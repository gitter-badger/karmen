import json
import re
from urllib import parse as urlparse
import requests

from server import app
from server.clients.utils import (
    PrinterClientAccessLevel,
    PrinterClientInfo,
    PrinterClient,
    PrinterClientException,
)


class Octoprint(PrinterClient):
    __client_name__ = "octoprint"

    def __init__(
        self,
        uuid,
        network_client_uuid,
        organization_uuid,
        protocol="http",
        hostname=None,
        ip=None,
        port=None,
        path="",
        token=None,
        name=None,
        client_props=None,
        printer_props=None,
        **kwargs
    ):
        self.uuid = uuid
        self.organization_uuid = organization_uuid
        self.network_client_uuid = network_client_uuid
        self.name = name
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.path = path
        self.token = token
        self.protocol = protocol
        self.printer_props = printer_props
        self.client = Octoprint.__client_name__
        self.network_base = ""
        self.update_network_base()

        if not client_props:
            client_props = {}
        self.client_info = PrinterClientInfo(
            version=client_props.get("version", None),
            connected=client_props.get("connected", False),
            access_level=client_props.get(
                "access_level", PrinterClientAccessLevel.PROTECTED
            ),
            api_key=client_props.get("api_key", None),
            webcam=client_props.get("webcam", None),
            plugins=client_props.get("plugins", []),
        )
        self.http_session = requests.Session()
        self.http_session.verify = app.config.get("NETWORK_VERIFY_CERTIFICATES", True)
        if self.client_info.api_key:
            self.http_session.headers.update({"X-Api-Key": self.client_info.api_key})

    def update_network_base(self):
        # TODO adapt requests to support custom DNS resolving that speaks mDNS/bonjour/avahi
        # https://stackoverflow.com/questions/22609385/python-requests-library-define-specific-dns
        # until then, we're stuck with IP addresses

        if self.token is not None and self.token != "":
            self.network_base = app.config.get("SOCKET_API_URL") % self.token
        else:
            if self.port is not None and self.port != 0:
                network_host = "%s:%s" % (self.ip, self.port)
            else:
                network_host = self.ip
            normalized_path = self.path
            if len(self.path) and self.path[-1] == "/":
                normalized_path = self.path[0:-1]
            self.network_base = urlparse.urljoin(
                "%s://%s" % (self.protocol, network_host), normalized_path
            )

    def get_printer_props(self):
        return self.printer_props

    def client_name(self):
        return self.client

    def add_api_key(self, api_key):
        self.client_info.api_key = api_key
        self.http_session.headers.update({"X-Api-Key": api_key})

    def _http_get(self, path, force=False):
        if not self.client_info.connected and not force:
            return None
        uri = "%s%s" % (self.network_base, path)
        try:
            req = self.http_session.get(
                uri, timeout=app.config.get("NETWORK_TIMEOUT", 10)
            )
            if req is None:
                self.client_info.connected = False
            elif bool(self.client_info.api_key):
                if req.status_code == 403:
                    self.client_info.access_level = PrinterClientAccessLevel.PROTECTED
                if req.status_code == 200:
                    self.client_info.access_level = PrinterClientAccessLevel.UNLOCKED
            return req
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            app.logger.debug("Cannot call %s because %s" % (uri, e))
            self.client_info.connected = False
            return None

    def _http_post(self, path, data=None, files=None, json=None, force=False):
        if not self.client_info.connected and not force:
            return None
        uri = "%s%s" % (self.network_base, path)
        try:
            headers = {}
            if self.client_info.api_key:
                headers.update({"X-Api-Key": self.client_info.api_key})
            # Because requests session shares the connection pool, timeout actually
            # does not get updated in the underlying reused socket.
            # That's why we're using a different connection with custom timeout.
            req = requests.post(
                uri,
                data=data,
                files=files,
                json=json,
                headers=headers,
                timeout=int(app.config.get("NETWORK_TIMEOUT", 10)) * 100,
                verify=app.config.get("NETWORK_VERIFY_CERTIFICATES", True),
            )
            if req is None:
                self.client_info.connected = False
            elif bool(self.client_info.api_key):
                if req.status_code == 403:
                    self.client_info.access_level = PrinterClientAccessLevel.PROTECTED
                if req.status_code == 200:
                    self.client_info.access_level = PrinterClientAccessLevel.UNLOCKED
            return req
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
        ) as e:
            app.logger.debug("Cannot call %s because %s" % (uri, e))
            self.client_info.connected = False
            return None

    def is_alive(self):
        request = self._http_get("/api/version", force=True)
        if request is not None and request.status_code in [200, 403]:
            if (
                not self.client_info.connected
                or request.status_code == 403
                or self.client_info.access_level == PrinterClientAccessLevel.UNKNOWN
            ):
                self.sniff()
            self.client_info.connected = True
        else:
            self.client_info.connected = False
        return self.client_info.connected

    def connect_printer(self):
        state_check = self.uncached_status()
        # printer is offline, it should be safe to do a connect attempt
        if state_check and state_check["state"] in [
            "Offline",
            "Closed",
            "Printer is not connected to Octoprint",
        ]:
            request = self._http_post("/api/connection", json={"command": "connect"})
            # TODO improve return value
            return bool(request is not None and request.status_code == 204)
        # printer is probably connected and operational/printing/etc.
        elif state_check and state_check["state"] not in [
            "Offline",
            "Closed",
            "Printer is not connected to Octoprint",
            "Printer is not responding",
        ]:
            return True
        return False

    def disconnect_printer(self):
        state_check = self.uncached_status()
        # printer is offline, it should be safe to do a connect attempt
        if state_check and state_check["state"] not in [
            "Offline",
            "Closed",
            "Printer is not responding",
            "Printer is not connected to Octoprint",
        ]:
            request = self._http_post("/api/connection", json={"command": "disconnect"})
            # TODO improve return value
            return bool(request is not None and request.status_code == 204)
        # printer is probably connected and operational/printing/etc.
        return True

    def sniff(self):
        """
        This can detect whether octoprint is alive and how it's access control is set up.
        In the future, this could detect different versions of octoprint as well.
        """
        request = self._http_get("/api/version", force=True)
        if request is None:
            app.logger.debug(
                "%s is not responding on /api/version - not octoprint"
                % self.network_base
            )
            self.client_info = PrinterClientInfo(
                {}, connected=False, api_key=self.client_info.api_key
            )
            return
        # This looks like octoprint with access control enabled
        if request.status_code == 403:
            app.logger.debug(
                "%s is responding with %s on /api/version - might be access-protected octoprint"
                % (self.network_base, request.status_code)
            )
            settings_req = self._http_get("/api/settings", force=True)
            # This might break with the future versions of octoprint
            # settings responds 200 when forcelogin plugin is disabled, but 403 when forcelogin is enabled
            if settings_req is not None and settings_req.status_code in [200, 403]:
                app.logger.debug(
                    "%s is responding with %s on /api/settings - probably access-protected octoprint"
                    % (self.network_base, settings_req.status_code)
                )
                try:
                    plugin_list = list(
                        dict(settings_req.json().get("plugins", {})).keys()
                    )
                except json.decoder.JSONDecodeError:
                    # This might happen when settings responds with 403
                    plugin_list = []
                self.client_info = PrinterClientInfo(
                    {},
                    connected=True,
                    access_level=PrinterClientAccessLevel.READ_ONLY
                    if settings_req.status_code == 200
                    else PrinterClientAccessLevel.PROTECTED,
                    api_key=self.client_info.api_key,
                    plugins=plugin_list,
                )
            else:
                app.logger.debug(
                    "%s is responding with %s on /api/settings - probably not octoprint"
                    % (self.network_base, settings_req.status_code)
                )
                self.client_info = PrinterClientInfo(
                    {},
                    connected=False,
                    api_key=self.client_info.api_key,
                    access_level=PrinterClientAccessLevel.UNKNOWN,
                )
            return
        # /api/version is not responding happily
        if request.status_code != 200:
            app.logger.debug(
                "%s is responding with %s on /api/version - not accessible"
                % (self.network_base, request.status_code)
            )
            self.client_info = PrinterClientInfo(
                {},
                connected=False,
                api_key=self.client_info.api_key,
                access_level=PrinterClientAccessLevel.UNKNOWN,
            )
            return
        # Try to parse /api/version response
        try:
            data = request.json()
            if "text" not in data:
                app.logger.debug(
                    "%s is responding with unfamiliar JSON %s on /api/version - probably not octoprint"
                    % (self.network_base, data)
                )
                self.client_info = PrinterClientInfo(
                    data,
                    connected=False,
                    api_key=self.client_info.api_key,
                    access_level=PrinterClientAccessLevel.UNKNOWN,
                )
                return
        except json.decoder.JSONDecodeError:
            app.logger.debug(
                "%s is not responding with JSON on /api/version - probably not octoprint"
                % self.network_base
            )
            self.client_info = PrinterClientInfo(
                {},
                connected=False,
                api_key=self.client_info.api_key,
                access_level=PrinterClientAccessLevel.UNKNOWN,
            )
            return
        if re.match(r"^octoprint", data.get("text"), re.IGNORECASE) is None:
            app.logger.debug(
                "%s is responding with %s on /api/version - probably not octoprint"
                % (self.network_base, data["text"])
            )
            self.client_info = PrinterClientInfo(
                data,
                connected=False,
                api_key=self.client_info.api_key,
                access_level=PrinterClientAccessLevel.UNKNOWN,
            )
            return
        self.client_info.connected = True
        settings_req = self._http_get("/api/settings", force=True)
        plugin_list = []
        if settings_req is not None:
            plugin_list = list(dict(settings_req.json().get("plugins", {})).keys())
        self.client_info = PrinterClientInfo(
            data,
            connected=True,
            api_key=self.client_info.api_key,
            access_level=PrinterClientAccessLevel.UNLOCKED,
            plugins=plugin_list,
            webcam=self.webcam(),
        )

    def status(self):
        return self.uncached_status(force=False)

    def uncached_status(self, force=True):
        request = self._http_get("/api/printer?exclude=history", force=force)
        if request is not None and request.status_code == 200:
            try:
                data = request.json()
                return {
                    "state": data["state"]["text"],
                    "temperature": data.get("temperature", {}),
                }
            except json.decoder.JSONDecodeError:
                return {
                    "state": "Printer is responding with invalid data",
                    "temperature": {},
                }
        elif request is not None and request.status_code == 409:
            return {"state": "Printer is not connected to Octoprint", "temperature": {}}
        else:
            return {"state": "Printer is not responding", "temperature": {}}

    def webcam(self):
        def parse_url(url):
            if url is None:
                return None
            if url.startswith("/"):
                return self.network_base + url
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "http://" + url
            parsed = urlparse.urlparse(url)
            port = parsed.port if parsed.port is not None else "80"
            if self.token is not None and self.token != "" and port != "80":
                return None  # Yet we can't sed other port's than 80 over ws api yet
            if self.token:
                # If we have ws api, we just try the path, not much else to do
                return "%s%s?%s" % (self.network_base, parsed.path, parsed.query)

            # Rest is only for local hub installations
            if parsed.hostname in ["localhost", "127.0.0.1"]:
                return "%s://%s:%s%s?%s" % (
                    parsed.scheme,
                    self.ip,
                    port,
                    parsed.path,
                    parsed.query,
                )
            return url

        request = self._http_get("/api/settings")
        if request is not None and request.status_code == 200:
            try:
                data = request.json()
                self.client_info.connected = True
                if "webcam" not in data or not data["webcam"]["webcamEnabled"]:
                    return {"message": "Webcam disabled in octoprint"}
                stream_url = data["webcam"].get("streamUrl", None)
                snapshot_url = data["webcam"].get("snapshotUrl", None)
                stream_url = parse_url(stream_url)
                snapshot_url = parse_url(snapshot_url)

                return {
                    "message": "OK",
                    "stream": stream_url,
                    "snapshot": snapshot_url,
                    "flipHorizontal": data["webcam"]["flipH"],
                    "flipVertical": data["webcam"]["flipV"],
                    "rotate90": data["webcam"]["rotate90"],
                }
            except json.decoder.JSONDecodeError:
                return {"message": "Cannot decode JSON"}
        else:
            return {"message": "Webcam not accessible"}

    def job(self):
        request = self._http_get("/api/job")
        if request is not None and request.status_code == 200:
            try:
                data = request.json()
                self.client_info.connected = True
                if "state" in data and re.match(r"Operational|Offline", data["state"]):
                    return {}
                return {
                    "name": data["job"]["file"].get("display", None),
                    "completion": data["progress"]["completion"],
                    "printTimeLeft": data["progress"]["printTimeLeft"],
                    "printTime": data["progress"]["printTime"],
                }
            except json.decoder.JSONDecodeError:
                return {}
        else:
            return {}

    def upload_and_start_job(self, gcode_disk_path, path=None):
        status = self.uncached_status()
        if self.client_info.connected and status["state"] != "Operational":
            raise PrinterClientException(
                "Printer is printing, cannot start another print"
            )
        request = self._http_post(
            "/api/files/local",
            files={"file": open(gcode_disk_path, "rb")},
            data={"path": "karmen" if not path else "karmen/%s" % path, "print": True},
        )
        # TODO improve return value
        return bool(request is not None and request.status_code == 201)

    def modify_current_job(self, action):
        if action not in ("cancel", "start", "toggle", "pause", "resume"):
            raise PrinterClientException("Action %s is not allowed" % (action,))
        body = {"command": action}
        if action in ["toggle", "pause", "resume"]:
            body = {"command": "pause", "action": action}
        request = self._http_post("/api/job", json=body)
        # TODO improve return value
        return bool(request is not None and request.status_code == 204)

    def are_lights_on(self):
        if "awesome_karmen_led" not in self.client_info.plugins:
            raise PrinterClientException(
                "awesome_karmen_led is not loaded in octoprint"
            )
        request = self._http_get("/api/plugin/awesome_karmen_led", force=True)
        if not request:
            return False
        try:
            data = request.json()
            color = data.get("color", [])
            is_on = False
            for c in color:
                if c > 0:
                    is_on = True
            return is_on
        except json.decoder.JSONDecodeError:
            return False

    def set_lights(self, color=None, heartbeat=None):
        if "awesome_karmen_led" not in self.client_info.plugins:
            raise PrinterClientException(
                "awesome_karmen_led is not loaded in octoprint"
            )
        body = {"command": "set_led"}
        if color is not None:
            body["color"] = color
        else:
            body["color"] = "black"

        if heartbeat is not None:
            body["heartbeat"] = heartbeat
        request = self._http_post("/api/plugin/awesome_karmen_led", json=body)
        if not request:
            return False
        try:
            data = request.json()
            return data.get("status", "NOK") == "OK"
        except json.decoder.JSONDecodeError:
            return False

    def move_head(self, movement, absolute=False):
        for axis in movement.keys():
            if axis not in ["x", "y", "z"]:
                return False
        command = {"absolute": absolute, "command": "jog"}
        command.update(movement)
        request = self._http_post("/api/printer/printhead", json=command)
        if not request or request.status_code != 204:
            return False
        return True

    def home_head(self, axes):
        for axis in axes:
            if axis not in ["x", "y", "z"]:
                return False
        command = {"axes": axes, "command": "home"}
        request = self._http_post("/api/printer/printhead", json=command)
        if not request or request.status_code != 204:
            return False
        return True

    def set_temperature(self, device, temp):
        path = "/api/printer/"
        if device in ["tool0", "tool1"]:
            path += "tool"
            command = {"targets": {device: temp}, "command": "target"}
        elif device == "bed":
            path += "bed"
            command = {"target": temp, "command": "target"}
        else:
            return False
        request = self._http_post(path, json=command)
        if not request or request.status_code != 204:
            return False
        return True

    def extrude(self, length):
        command = {"amount": length, "command": "extrude"}
        request = self._http_post("/api/printer/tool", json=command)
        if not request or request.status_code != 204:
            return False
        return True

    def set_fan(self, state):
        command = {
            "commands": ["M106 " + ("S255" if state == "on" else "S0")],
            "parameters": {},
        }
        request = self._http_post("/api/printer/command", json=command)
        if not request or request.status_code != 204:
            return False
        return True

    def motors_off(self):
        command = {"commands": ["M18"], "parameters": {}}
        request = self._http_post("/api/printer/command", json=command)
        if not request or request.status_code != 204:
            return False
        return True

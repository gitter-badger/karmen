const BASE_URL = window.env.BACKEND_BASE;

export const getGcodes = (startWith = null, orderBy = null, displayFilter = null, limit = 15, fields = []) => {
  let uri = `${BASE_URL}/gcodes?limit=${limit}`;
  if (fields) {
    uri += `&fields=${fields.join(',')}`;
  }
  if (startWith) {
    uri += `&start_with=${startWith}`;
  }
  if (orderBy) {
    uri += `&order_by=${orderBy}`;
  }
  if (displayFilter) {
    uri += `&filter=display:${displayFilter}`;
  }
  return fetch(uri)
    .then((response) => {
      if (response.status !== 200) {
        console.error(`Cannot get list of gcodes: ${response.status}`);
        return {
          "items": []
        };
      }
      return response.json();
    }).catch((e) => {
      console.error(`Cannot get list of gcodes: ${e}`);
      return {
        "items": []
      };
    });
}

export const getGcode = (id, fields = []) => {
  let uri = `${BASE_URL}/gcodes/${id}`;
  if (fields && fields.length) {
    uri += `?fields=${fields.join(',')}`;
  }
  return fetch(uri)
    .then((response) => {
      if (response.status !== 200) {
        console.error(`Cannot get a gcode: ${response.status}`);
        return;
      }
      return response.json();
    }).catch((e) => {
      console.error(`Cannot get a gcode: ${e}`);
      return {};
    })
}

export const deleteGcode = (id) => {
  return fetch(`${BASE_URL}/gcodes/${id}`, {
    method: 'DELETE',
  })
    .then((response) => {
      if (response.status !== 204) {
        console.error(`Cannot remove a gcode: ${response.status}`);
      }
      return response.status;
    }).catch((e) => {
      console.error(`Cannot remove a gcode: ${e}`);
      return 500;
    });
}

export const uploadGcode = (path, file) => {
  var data = new FormData();
  data.append('file', file);
  data.append('path', path);
  return fetch(`${BASE_URL}/gcodes`, {
    method: 'POST',
    body: data,
  })
    .then((response) => {
      if (response.status !== 201) {
        console.error(`Cannot add a gcode: ${response.status}`);
      }
      return response.status;
    }).catch((e) => {
      console.error(`Cannot add a gcode: ${e}`);
      return 500;
    });
}


export const printGcode = (id, printer) => {
  return fetch(`${BASE_URL}/printjobs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      gcode: id,
      printer: printer,
    }),
  })
    .then((response) => {
      if (response.status !== 201) {
        console.error(`Cannot start a printjob: ${response.status}`);
      }
      return response.status;
    }).catch((e) => {
      console.error(`Cannot start a printjob: ${e}`);
      return 500;
    });
}

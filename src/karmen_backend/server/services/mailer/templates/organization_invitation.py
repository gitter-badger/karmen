from textwrap import dedent
from server import app
from .mail_template import MailTemplate


class OrganizationInvitation(MailTemplate):
    def subject(self):
        return "Karmen - Organization invitation"

    def prepare_variables(self, variables={}):
        self.variables = variables
        # TODO Actually deeplink into organization - does it survive frontend login though?
        self.variables["organization_link"] = "%s" % (self.get_base_url())

    def textbody(self):
        return (
            dedent(
                """
            You have been invited to join %s

            %s has invited you to join the %s on Karmen.

            Visit the application on %s

            © 2020 Fragaria s.r.o.
            """
            )
            % (
                self.variables["organization_name"],
                self.variables["inviter_username"],
                self.variables["organization_name"],
                self.variables["organization_link"],
            )
        )

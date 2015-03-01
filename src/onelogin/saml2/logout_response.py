# -*- coding: utf-8 -*-

""" OneLogin_Saml2_Logout_Response class

Copyright (c) 2014, OneLogin, Inc.
All rights reserved.

Logout Response class of OneLogin's Python Toolkit.

"""

from onelogin.saml2.constants import OneLogin_Saml2_Constants
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from onelogin.saml2.xml_utils import OneLogin_Saml2_XML


class OneLogin_Saml2_Logout_Response(object):
    """

    This class  handles a Logout Response. It Builds or parses a Logout Response object
    and validates it.

    """

    def __init__(self, settings, response=None):
        """
        Constructs a Logout Response object (Initialize params from settings
        and if provided load the Logout Response.

        Arguments are:
            * (OneLogin_Saml2_Settings)   settings. Setting data
            * (string)                    response. An UUEncoded SAML Logout
                                                    response from the IdP.
        """
        self.__settings = settings
        self.__error = None

        if response is not None:
            self.__logout_response = OneLogin_Saml2_Utils.decode_base64_and_inflate(response)
            self.document = OneLogin_Saml2_XML.to_etree(self.__logout_response)

    def get_issuer(self):
        """
        Gets the Issuer of the Logout Response Message
        :return: The Issuer
        :rtype: string
        """
        issuer = None
        issuer_nodes = self.__query('/samlp:LogoutResponse/saml:Issuer')
        if len(issuer_nodes) == 1:
            issuer = issuer_nodes[0].text
        return issuer

    def get_status(self):
        """
        Gets the Status
        :return: The Status
        :rtype: string
        """
        entries = self.__query('/samlp:LogoutResponse/samlp:Status/samlp:StatusCode')
        if len(entries) == 0:
            return None
        status = entries[0].attrib['Value']
        return status

    def is_valid(self, request_data, request_id=None):
        """
        Determines if the SAML LogoutResponse is valid
        :param request_id: The ID of the LogoutRequest sent by this SP to the IdP
        :type request_id: string
        :return: Returns if the SAML LogoutResponse is or not valid
        :rtype: boolean
        """
        self.__error = None
        try:
            idp_data = self.__settings.get_idp_data()
            idp_entity_id = idp_data['entityId']
            get_data = request_data['get_data']

            if self.__settings.is_strict():
                res = OneLogin_Saml2_XML.validate_xml(self.document, 'saml-schema-protocol-2.0.xsd', self.__settings.is_debug_active())
                if isinstance(res, str):
                    raise Exception('Invalid SAML Logout Request. Not match the saml-schema-protocol-2.0.xsd')

                security = self.__settings.get_security_data()

                # Check if the InResponseTo of the Logout Response matchs the ID of the Logout Request (requestId) if provided
                in_response_to = self.document.get('InResponseTo', None)
                if request_id is not None and in_response_to and in_response_to != request_id:
                    raise Exception('The InResponseTo of the Logout Response: %s, does not match the ID of the Logout request sent by the SP: %s' % (in_response_to, request_id))

                # Check issuer
                issuer = self.get_issuer()
                if issuer is not None and issuer != idp_entity_id:
                    raise Exception('Invalid issuer in the Logout Request')

                current_url = OneLogin_Saml2_Utils.get_self_url_no_query(request_data)

                # Check destination
                destination = self.document.get('Destination', None)
                if destination and current_url not in destination:
                    raise Exception('The LogoutRequest was received at $currentURL instead of $destination')

                if security['wantMessagesSigned']:
                    if 'Signature' not in get_data:
                        raise Exception('The Message of the Logout Response is not signed and the SP require it')

            if 'Signature' in get_data:
                sign_alg = get_data.get('SigAlg', OneLogin_Saml2_Constants.RSA_SHA1)
                if sign_alg != OneLogin_Saml2_Constants.RSA_SHA1:
                    raise Exception('Invalid signAlg in the recieved Logout Response')

                signed_query = 'SAMLResponse=%s' % OneLogin_Saml2_Utils.escape_url(get_data['SAMLResponse'])
                if 'RelayState' in get_data:
                    signed_query = '%s&RelayState=%s' % (signed_query, OneLogin_Saml2_Utils.escape_url(get_data['RelayState']))
                signed_query = '%s&SigAlg=%s' % (signed_query, OneLogin_Saml2_Utils.escape_url(sign_alg))

                cert = idp_data['x509cert']
                if not cert:
                    raise Exception('In order to validate the sign on the Logout Response, the x509cert of the IdP is required')

                if not OneLogin_Saml2_Utils.validate_binary_sign(signed_query, OneLogin_Saml2_Utils.b64decode(get_data['Signature']), cert):
                    raise Exception('Signature validation failed. Logout Response rejected')

            return True
        # pylint: disable=R0801
        except Exception as err:
            self.__error = str(err)
            debug = self.__settings.is_debug_active()
            if debug:
                print(err)
            return False

    def __query(self, query):
        """
        Extracts a node from the Etree (Logout Response Message)
        :param query: Xpath Expression
        :type query: string
        :return: The queried node
        :rtype: Element
        """
        return OneLogin_Saml2_XML.query(self.document, query)

    def build(self, in_response_to):
        """
        Creates a Logout Response object.
        :param in_response_to: InResponseTo value for the Logout Response.
        :type in_response_to: string
        """
        sp_data = self.__settings.get_sp_data()
        idp_data = self.__settings.get_idp_data()

        uid = OneLogin_Saml2_Utils.generate_unique_id()
        issue_instant = OneLogin_Saml2_Utils.parse_time_to_SAML(OneLogin_Saml2_Utils.now())

        logout_response = """<samlp:LogoutResponse xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                      xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                      ID="%(id)s"
                      Version="2.0"
                      IssueInstant="%(issue_instant)s"
                      Destination="%(destination)s"
                      InResponseTo="%(in_response_to)s"
>
    <saml:Issuer>%(entity_id)s</saml:Issuer>
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success" />
    </samlp:Status>
</samlp:LogoutResponse>""" % \
            {
                'id': uid,
                'issue_instant': issue_instant,
                'destination': idp_data['singleLogoutService']['url'],
                'in_response_to': in_response_to,
                'entity_id': sp_data['entityId'],
            }

        self.__logout_response = logout_response

    def get_response(self):
        """
        Returns a Logout Response object.
        :return: Logout Response deflated and base64 encoded
        :rtype: string
        """
        return OneLogin_Saml2_Utils.deflate_and_base64_encode(self.__logout_response)

    def get_error(self):
        """
        After execute a validation process, if fails this method returns the cause
        """
        return self.__error

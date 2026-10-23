# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Fake Bejerman SOAP server and connector builders shared by the Bejerman tests.

Profile addons import it and answer their own query views through
``query_view``.
"""

import json
import re
from datetime import date
from unittest.mock import MagicMock, patch
from xml.sax.saxutils import escape

from lxml import etree

from odoo.addons.collection.tests.test_collection_payment import insert_company_like

_SESSION_TOKEN = "SESSIONTOKENDEADBEEFCAFE"
_CLAVE = "hunter2-bejerman-clave"
_USUARIO = "ADMIN"
_ERROR_MSG = "Operacion de prueba rechazada"
_WS_URL = "https://erp.secret.example/Bejerman-SDK-WS/EFlexSDK_Service.svc"
_WS_URL_B = "https://erp-b.other.example/Bejerman-SDK-WS/EFlexSDK_Service.svc"
_SOAPACTION_REGISTRO = "http://localhost:57213/IEFlexSDK_Service/EFlexSDK_WSRegistro"
_SOAPACTION_EJECUTAR = "http://localhost:57213/IEFlexSDK_Service/EFlexSDK_WSEjecutar"
_SOAPACTION_CIERRE = "http://localhost:57213/IEFlexSDK_Service/EFlexSDK_WSCierreProceso"

_REGISTRO_OK = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <EFlexSDK_WSRegistroResponse xmlns="http://localhost:57213/">
      <EFlexSDK_WSRegistroResult
        xmlns:a="http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:DatosJSON i:nil="true"/>
        <a:ErrorMsg i:nil="true"/>
        <a:EsLista i:nil="true"/>
        <a:NombreTipoDatos>string</a:NombreTipoDatos>
        <a:Resultado>OK</a:Resultado>
        <a:Token>{_SESSION_TOKEN}</a:Token>
      </EFlexSDK_WSRegistroResult>
    </EFlexSDK_WSRegistroResponse>
  </s:Body>
</s:Envelope>
"""

_EJECUTAR_ERROR = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <EFlexSDK_WSEjecutarResponse xmlns="http://localhost:57213/">
      <EFlexSDK_WSEjecutarResult
        xmlns:a="http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:DatosJSON i:nil="true"/>
        <a:ErrorMsg>{_ERROR_MSG}</a:ErrorMsg>
        <a:EsLista i:nil="true"/>
        <a:NombreTipoDatos i:nil="true"/>
        <a:Resultado>ERROR</a:Resultado>
        <a:Token i:nil="true"/>
      </EFlexSDK_WSEjecutarResult>
    </EFlexSDK_WSEjecutarResponse>
  </s:Body>
</s:Envelope>
"""

_REGISTRO_ERROR = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <EFlexSDK_WSRegistroResponse xmlns="http://localhost:57213/">
      <EFlexSDK_WSRegistroResult
        xmlns:a="http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:DatosJSON i:nil="true"/>
        <a:ErrorMsg>{_ERROR_MSG}</a:ErrorMsg>
        <a:EsLista i:nil="true"/>
        <a:NombreTipoDatos i:nil="true"/>
        <a:Resultado>ERROR</a:Resultado>
        <a:Token i:nil="true"/>
      </EFlexSDK_WSRegistroResult>
    </EFlexSDK_WSRegistroResponse>
  </s:Body>
</s:Envelope>
"""

_CIERRE_OK = """\
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <EFlexSDK_WSCierreProcesoResponse xmlns="http://localhost:57213/">
      <EFlexSDK_WSCierreProcesoResult
        xmlns:a="http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:DatosJSON i:nil="true"/>
        <a:ErrorMsg i:nil="true"/>
        <a:EsLista i:nil="true"/>
        <a:NombreTipoDatos i:nil="true"/>
        <a:Resultado>OK</a:Resultado>
        <a:Token i:nil="true"/>
      </EFlexSDK_WSCierreProcesoResult>
    </EFlexSDK_WSCierreProcesoResponse>
  </s:Body>
</s:Envelope>
"""


_UNAVAILABLE = "The requested connector operation is not available."
_NOT_CONFIGURED = "The collection connector is not configured."
_REFRESH_FAILED = (
    "The Bejerman debt snapshot could not be refreshed. The previous snapshot was kept."
)
_NO_DEBT_SOURCE = (
    "The Bejerman connector has no debt source. "
    "Choose the Bejerman profile of its customer."
)
_BEJERMAN_CONFIG_FIELDS = (
    "bejerman_ws_url",
    "bejerman_usuario",
    "bejerman_clave",
    "bejerman_empresa",
    "bejerman_puesto",
    "bejerman_sucursal",
    "bejerman_timeout",
    "bejerman_deadline",
    "bejerman_allow_insecure",
    "bejerman_ca_bundle",
)
_LEAK_TOKENS = (
    _ERROR_MSG,
    _SESSION_TOKEN,
    _CLAVE,
    _USUARIO,
    _WS_URL,
    _WS_URL_B,
    "ErrorMsg",
    "Token",
    "xClave",
    "SOAP",
    "SOAPAction",
    "s:Envelope",
    "Envelope",
    "ObtenerClientes",
    "ObtenerJsonQueryVista",
    "EFlexSDK",
    "SELECT",
    "INSERT",
    "UPDATE",
)
_SELLER_KEYS = frozenset({"id", "name", "mobile", "active", "commission_percent"})
_CUSTOMER_KEYS = frozenset({"id", "name", "identification", "customer_code", "active"})
_INVOICE_KEYS = frozenset(
    {
        "id",
        "number",
        "issue_date",
        "due_date",
        "amount",
        "balance",
        "amount_untaxed",
        "state",
        "document_kind",
    }
)

_CLIENTES = [
    {
        "Cliente_Codigo": "000123",
        "Cliente_RazonSocial": "Acme SA",
        "Cliente_CUIT": "20123456789",
        "Cliente_Habilitado": True,
        "Cliente_VendedorCodigo": "000E",
    },
    {
        "Cliente_Codigo": "000124",
        "Cliente_RazonSocial": "Other Seller Co",
        "Cliente_CUIT": "27987654321",
        "Cliente_Habilitado": True,
        "Cliente_VendedorCodigo": "00G",
    },
    {
        "Cliente_Codigo": "000125",
        "Cliente_RazonSocial": "Inactive Acme",
        "Cliente_CUIT": "23000000009",
        "Cliente_Habilitado": False,
        "Cliente_VendedorCodigo": "000E",
    },
]
_TODAY = date(2026, 2, 15)


def _xml_response(xml_text):
    response = MagicMock()
    response.content = xml_text.encode("utf-8")
    response.status_code = 200
    response.raise_for_status.return_value = None
    return response


def _call_soap_action(call):
    headers = call.kwargs["headers"]
    return headers["SOAPAction"].strip().strip('"')


def _call_body(call):
    content = call.kwargs["content"]
    if isinstance(content, bytes):
        return content.decode("utf-8")
        return str(content)


def _ejecutar_ok(payload, double_encoded=False):
    """Build an OK Ejecutar response; Query views arrive JSON-in-JSON."""
    text = json.dumps(payload, ensure_ascii=False)
    if double_encoded:
        text = json.dumps(text, ensure_ascii=False)
    datos = escape(text)
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <EFlexSDK_WSEjecutarResponse xmlns="http://localhost:57213/">
      <EFlexSDK_WSEjecutarResult
        xmlns:a="http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance">
        <a:DatosJSON>{datos}</a:DatosJSON>
        <a:ErrorMsg i:nil="true"/>
        <a:EsLista>N</a:EsLista>
        <a:NombreTipoDatos>List`1</a:NombreTipoDatos>
        <a:Resultado>OK</a:Resultado>
        <a:Token i:nil="true"/>
      </EFlexSDK_WSEjecutarResult>
    </EFlexSDK_WSEjecutarResponse>
  </s:Body>
</s:Envelope>
"""


def _parametros_json(body):
    match = re.search(
        r"<[^>]*ParametrosJson[^>]*>(.*?)</",
        body,
        flags=re.DOTALL,
    )
    if not match or not match.group(1).strip():
        return None
    text = (
        match.group(1)
        .strip()
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )
    return json.loads(text)


def _erp_post(
    url,
    content=None,
    headers=None,
    payloads_by_url=None,
    fail=(),
    query_view=None,
    **_kwargs,
):
    """Answer one SOAP POST like the ERP would.

    ``query_view(scenario, view, pack, fail)`` answers ObtenerJsonQueryVista with
    an XML text, or None for a view the ERP does not have (an error answer).
    """
    del headers
    body = content.decode("utf-8") if isinstance(content, bytes) else str(content or "")
    pack = (payloads_by_url or {}).get(url) or (payloads_by_url or {}).get("*") or {}
    clientes = pack.get("clientes", _CLIENTES)
    fail = set(fail)
    if "EFlexSDK_WSCierreProceso" in body:
        return _xml_response(_CIERRE_OK)
    if "EFlexSDK_WSRegistro" in body and "EFlexSDK_WSEjecutar" not in body:
        if "Registro" in fail:
            return _xml_response(_REGISTRO_ERROR)
        return _xml_response(_REGISTRO_OK)
    if "ObtenerClientes" in body:
        if "ObtenerClientes" in fail:
            return _xml_response(_EJECUTAR_ERROR)
        return _xml_response(_ejecutar_ok(clientes))
    if "ObtenerJsonQueryVista" in body and query_view is not None:
        params = _parametros_json(body) or []
        view = params[1] if len(params) > 1 else ""
        scenario = params[0] if params else ""
        answer = query_view(scenario, view, pack, fail)
        if answer is not None:
            return _xml_response(answer)
    return _xml_response(_EJECUTAR_ERROR)


def _patch_httpx(payloads_by_url=None, fail=(), query_view=None):
    def _post(url, content=None, headers=None, **kwargs):
        return _erp_post(
            url,
            content=content,
            headers=headers,
            payloads_by_url=payloads_by_url,
            fail=fail,
            query_view=query_view,
            **kwargs,
        )

    return patch(
        "odoo.addons.collection_connector_bejerman.service.session.httpx.Client.post",
        side_effect=_post,
    )


def _patch_today(connector, today=_TODAY):
    """Pin the company-timezone "today".

    A plain function, not a MagicMock: the ORM scans model attributes for
    `_ondelete`/`_constrains` markers and a mock answers every attribute name.
    """
    return patch.object(type(connector), "_bejerman_today", new=lambda _self: today)


class BejermanTestMixin:
    """Shared connector builders for the Bejerman test cases."""

    def _partner_has_autopost_bills_column(self):
        """`account`'s NOT NULL column may outlive its field in this registry."""
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = 'res_partner'
               AND column_name = 'autopost_bills'
            """
        )
        return bool(self.env.cr.fetchone())

    def _create_bare_partner(self, name, is_company=False):
        """Create a partner whether or not `account` is in this database.

        `account` is not a dependency. With it loaded, `autopost_bills` goes
        through the ORM; when its column outlives the field, the row is
        inserted by SQL; without the column, it is a plain ORM create.
        """
        Partner = self.env["res.partner"].with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
            mail_create_nosubscribe=True,
        )
        email = f"{name}@example.com"
        vals = {"name": name, "email": email, "is_company": is_company}
        if "autopost_bills" in Partner._fields:
            vals["autopost_bills"] = "ask"
            return Partner.create(vals)
        if not self._partner_has_autopost_bills_column():
            return Partner.create(vals)
        self.env.cr.execute(
            """
            INSERT INTO res_partner (
                name, email, active, complete_name, type, is_company,
                autopost_bills, create_uid, write_uid, create_date, write_date
            )
            VALUES (
                %s, %s, true, %s, 'contact', %s, 'ask',
                1, 1,
                (now() AT TIME ZONE 'UTC'),
                (now() AT TIME ZONE 'UTC')
            )
            RETURNING id
            """,
            (name, email, name, is_company),
        )
        partner = Partner.browse(self.env.cr.fetchone()[0])
        partner.invalidate_recordset()
        return partner

    def _create_company(self, name):
        partner = self._create_bare_partner(name, is_company=True)
        return insert_company_like(self.env, name, partner.id)

    def _bejerman_vals(self, **overrides):
        vals = {
            "name": "Bejerman Connector",
            "type": "bejerman",
            "bejerman_ws_url": _WS_URL,
            "bejerman_usuario": _USUARIO,
            "bejerman_clave": _CLAVE,
            "bejerman_empresa": "MODE",
            "bejerman_puesto": "1",
            "bejerman_sucursal": "",
            "bejerman_timeout": 60,
            "bejerman_allow_insecure": False,
        }
        vals.update(overrides)
        return vals

    def _make_connector(self, **overrides):
        return self.env["collection.connector"].create(self._bejerman_vals(**overrides))

    def _patch_erp(self, **kwargs):
        """Patch the HTTP client with the canned ERP; profiles add their views."""
        return _patch_httpx(**kwargs)

    def _refresh(self, connector, **kwargs):
        """Refresh the debt snapshot against the canned ERP; return the POST mock."""
        with self._patch_erp(**kwargs) as mock_post:
            connector._bejerman_refresh_snapshot()
        return mock_post

    def _assert_no_leak(self, message, *extra):
        for token in _LEAK_TOKENS + extra:
            if token:
                self.assertNotIn(token, message)

    def _assert_clean_user_error(self, exc, *extra):
        message = str(exc)
        self.assertEqual(message, _NOT_CONFIGURED)
        self._assert_no_leak(message, *extra)

    def _form_arch_for(self, user):
        result = (
            self.env["collection.connector"].with_user(user).get_view(view_type="form")
        )
        return etree.fromstring(result["arch"])

    def _create_user(self, login, *group_xmlids):
        partner = self._create_bare_partner(login)
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True, tracking_disable=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "email": partner.email,
                    "partner_id": partner.id,
                    "group_ids": [
                        (6, 0, [self.env.ref(xmlid).id for xmlid in group_xmlids])
                    ],
                }
            )
        )

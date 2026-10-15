# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""SOAP 1.1 envelopes for Registro / Ejecutar / CierreProceso (no zeep)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from .errors import BejermanError, BejermanTransportError

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
OPS_NS = "http://localhost:57213/"
DATACONTRACT_NS = "http://schemas.datacontract.org/2004/07/SB.NET.eFlex.SDKWS"
ARRAYS_NS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"

SOAPACTION_REGISTRO = f"{OPS_NS}IEFlexSDK_Service/EFlexSDK_WSRegistro"
SOAPACTION_EJECUTAR = f"{OPS_NS}IEFlexSDK_Service/EFlexSDK_WSEjecutar"
SOAPACTION_CIERRE = f"{OPS_NS}IEFlexSDK_Service/EFlexSDK_WSCierreProceso"

CONTENT_TYPE = "text/xml; charset=utf-8"

ET.register_namespace("soapenv", SOAP_NS)
ET.register_namespace("loc", OPS_NS)
ET.register_namespace("sb", DATACONTRACT_NS)
ET.register_namespace("arr", ARRAYS_NS)

_RESULT_TAGS = frozenset(
    {"Resultado", "Token", "DatosJSON", "ErrorMsg", "EsLista", "NombreTipoDatos"}
)
_REDACT_VALUE = re.compile(
    r"(<(?:[\w.-]+:)?(?:Token|xClave)(?:\s[^>]*)?>)[^<]*",
    re.IGNORECASE,
)


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _local(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _sub(parent: ET.Element, ns: str, tag: str, text: str | None = None) -> ET.Element:
    el = ET.SubElement(parent, _qn(ns, tag))
    if text:
        el.text = text
    return el


def _tostring(root: ET.Element) -> str:
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def _envelope() -> tuple[ET.Element, ET.Element]:
    envelope = ET.Element(_qn(SOAP_NS, "Envelope"))
    ET.SubElement(envelope, _qn(SOAP_NS, "Header"))
    body = ET.SubElement(envelope, _qn(SOAP_NS, "Body"))
    return envelope, body


def _parameters(parent: ET.Element) -> None:
    parameters = _sub(parent, DATACONTRACT_NS, "Parametros")
    ET.SubElement(parameters, _qn(ARRAYS_NS, "anyType"))


def _xrequest(
    parent: ET.Element,
    circuit: str,
    operation: str,
    parameters_json_text: str,
    token: str,
) -> ET.Element:
    xrequest = _sub(parent, OPS_NS, "xRequest")
    _sub(xrequest, DATACONTRACT_NS, "Circuito", circuit)
    _sub(xrequest, DATACONTRACT_NS, "Operacion", operation)
    _parameters(xrequest)
    _sub(xrequest, DATACONTRACT_NS, "ParametrosJson", parameters_json_text)
    _sub(xrequest, DATACONTRACT_NS, "Token", token)
    return xrequest


def build_register(
    user: str,
    password: str,
    company: str,
    workstation: str,
    branch: str = "",
) -> str:
    envelope, body = _envelope()
    op = _sub(body, OPS_NS, "EFlexSDK_WSRegistro")
    _sub(op, OPS_NS, "xUsuario", user)
    _sub(op, OPS_NS, "xClave", password)
    _sub(op, OPS_NS, "xCodEmpresa", company)
    _sub(op, OPS_NS, "xPtoTrabajo", workstation)
    _sub(op, OPS_NS, "xCodSucursal", branch)
    return _tostring(envelope)


def build_execute(
    circuit: str,
    operation: str,
    parameters_json_text: str,
    token: str,
) -> str:
    envelope, body = _envelope()
    op = _sub(body, OPS_NS, "EFlexSDK_WSEjecutar")
    _xrequest(op, circuit, operation, parameters_json_text, token)
    return _tostring(envelope)


def build_close(token: str, circuit: str = "", operation: str = "") -> str:
    envelope, body = _envelope()
    op = _sub(body, OPS_NS, "EFlexSDK_WSCierreProceso")
    _xrequest(op, circuit, operation, "", token)
    return _tostring(envelope)


def redact_soap(xml_text: str, password: str = "") -> str:
    """Replace Token and xClave element text (and the password if it appears)."""
    redacted = _REDACT_VALUE.sub(r"\1***", xml_text)
    if password:
        redacted = redacted.replace(password, "***")
    return redacted


def _is_nil(el: ET.Element) -> bool:
    for key, value in el.attrib.items():
        if _local(key) == "nil" and str(value).lower() == "true":
            return True
    return False


def _el_text(el: ET.Element | None) -> str | None:
    if el is None or _is_nil(el):
        return None
    if el.text is None:
        return ""
    return el.text


@dataclass
class SoapResult:
    resultado: str | None
    token: str | None
    datos_json: str | None
    error_msg: str | None
    es_lista: str | None = None
    nombre_tipo_datos: str | None = None


def parse_response(xml_bytes: bytes | str) -> SoapResult:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise BejermanTransportError("Unparseable SOAP response") from exc

    has_fault = False
    found: dict[str, ET.Element] = {}
    for el in root.iter():
        name = _local(el.tag)
        if name == "Fault":
            has_fault = True
        elif name in _RESULT_TAGS and name not in found:
            found[name] = el

    if has_fault:
        raise BejermanError("SOAP Fault")

    if "Resultado" not in found:
        raise BejermanTransportError("SOAP response missing Resultado")

    resultado = _el_text(found.get("Resultado"))
    if resultado is not None:
        resultado = resultado.strip()
    error_msg = _el_text(found.get("ErrorMsg"))
    if error_msg is not None:
        error_msg = error_msg.strip() or None
    token = _el_text(found.get("Token"))
    if token is not None:
        token = token.strip() or None
    datos_json = _el_text(found.get("DatosJSON"))
    es_lista = _el_text(found.get("EsLista"))
    if es_lista is not None:
        es_lista = es_lista.strip() or None
    nombre_tipo_datos = _el_text(found.get("NombreTipoDatos"))
    if nombre_tipo_datos is not None:
        nombre_tipo_datos = nombre_tipo_datos.strip() or None

    return SoapResult(
        resultado=resultado,
        token=token,
        datos_json=datos_json,
        error_msg=error_msg,
        es_lista=es_lista,
        nombre_tipo_datos=nombre_tipo_datos,
    )

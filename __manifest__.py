# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Collections Bejerman Connector",
    "version": "19.0.1.3.0",
    "category": "Sales/CRM",
    "summary": "Read-only Bejerman seller, customer, and debt source for Collections",
    "author": "Seedian",
    "website": "https://seedian.ai",
    "depends": ["collection"],
    "external_dependencies": {
        "python": ["httpx"],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/collection_connector_bejerman_security.xml",
        "views/collection_connector_bejerman_seller_enable_views.xml",
        "views/collection_connector_views.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
    "license": "AGPL-3",
}

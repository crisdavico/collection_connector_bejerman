# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# The Kras settings and untaxed amounts moved to collection_connector_bejerman_kras.
# Their fields are handed to that addon before this upgrade ends: a field whose
# only owner is an upgraded addon that no longer defines it is dropped with its
# column, so upgrading this addon before (or without) installing the Kras addon
# would lose the Kras connector's settings. Installing the Kras addon later finds
# the fields, and their data, already its own.
MOVED_FIELDS = (
    "field_collection_connector__bejerman_debt_scenario",
    "field_collection_connector__bejerman_debt_view",
    "field_collection_connector__bejerman_quotation_kinds",
    "field_collection_connector__bejerman_debt_filter_field",
    "field_collection_connector__bejerman_untaxed_scenario",
    "field_collection_connector__bejerman_untaxed_view",
    "field_collection_connector_bejerman_debt__amount_untaxed",
    "field_collection_connector_bejerman_debt__balance_untaxed",
)


def migrate(cr, version):
    if not version:
        return
    # When the Kras addon already holds an xmlid of the same name (it was
    # installed first), the base's row is left alone; the normal end-of-upgrade
    # cleanup removes it, and the field stays the Kras addon's.
    cr.execute(
        """
        UPDATE ir_model_data base
           SET module = 'collection_connector_bejerman_kras'
         WHERE base.module = 'collection_connector_bejerman'
           AND base.model = 'ir.model.fields'
           AND base.name IN %s
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data kras
                 WHERE kras.module = 'collection_connector_bejerman_kras'
                   AND kras.model = 'ir.model.fields'
                   AND kras.name = base.name
           )
        """,
        (MOVED_FIELDS,),
    )

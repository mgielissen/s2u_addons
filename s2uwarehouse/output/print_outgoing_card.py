from odoo import api, models


class PrintOutgoingCard(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_outgoing_card'

    @api.model
    def get_report_values(self, docids, data=None):
        parent_ids = []
        unit_ids = []
        parent_trans_ids = {}
        unit_trans_ids = {}
        for out in self.env['s2u.warehouse.outgoing'].browse(docids):
            for trans in out.trans_ids:
                if trans.parent_id and trans.parent_id.name not in parent_ids and trans.parent_id.type == 'pallet':
                    parent_ids.append(trans.parent_id.name)
                    parent_trans_ids[trans.parent_id.name] = []
                    parent_trans_ids[trans.parent_id.name].append(trans)
                if trans.parent_id and trans.parent_id.name in parent_ids and trans.parent_id.type == 'pallet':
                    if trans not in parent_trans_ids[trans.parent_id.name]:
                        parent_trans_ids[trans.parent_id.name].append(trans)
                if not trans.parent_id and trans.unit_id and trans.unit_id not in unit_ids and trans.unit_id.type == 'pallet':
                    unit_ids.append(trans.unit_id.name)
                    unit_trans_ids[trans.unit_id.name] = []
                    unit_trans_ids[trans.unit_id.name].append(trans)
                if not trans.parent_id and trans.unit_id and trans.unit_id in unit_ids and trans.unit_id.type == 'pallet':
                    if trans not in unit_trans_ids[trans.unit_id.name]:
                        unit_trans_ids[trans.unit_id.name].append(trans)

        list_parent_trans = []
        for parent_id in parent_ids:
            trans_datas = {}
            trans_datas[parent_id] = {}
            for parent in parent_trans_ids[parent_id]:
                trans_datas[parent_id][parent.id] = {}
                trans_datas[parent_id][parent.id]['name'] = parent.unit_id.name
                trans_datas[parent_id][parent.id]['product'] = parent.product_id.product_id.name
                trans_datas[parent_id][parent.id]['qty'] = parent.qty * -1
            #print trans_datas
            list_parent_trans.append(trans_datas)

        list_unit_trans = []
        for unit_id in unit_ids:
            trans_datas = {}
            trans_datas[unit_id] = {}
            for unit in unit_trans_ids[unit_id]:
                trans_datas[unit_id][unit.id] = {}
                trans_datas[unit_id][unit.id]['name'] = unit.unit_id.name
                trans_datas[unit_id][unit.id]['product'] = unit.product_id.product_id.name
                trans_datas[unit_id][unit.id]['qty'] = unit.qty * -1
            #print trans_datas
            list_parent_trans.append(trans_datas)

        return {
            'doc_ids': docids,
            'doc_model': 's2u.warehouse.outgoing',
            'docs': self.env['s2u.warehouse.outgoing'].browse(docids),
            'trans_list': list_parent_trans,
            'unit_list': list_unit_trans
        }


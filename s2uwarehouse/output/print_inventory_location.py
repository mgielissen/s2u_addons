from odoo import api, models


class PrintInventoryLocation(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_inventory_location'

    @api.model
    def get_report_values(self, docids, data=None):

        def keyindict(key_search, dict):
            for key, value in sorted(iter(dict.items())):
                if key == key_search:
                    return value
            return False

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        location_list = {}
        product_metadata = {}

        transactions = trans_obj.search([('transaction_date', '<=', data['form']['date_till'])], order='product_id asc')

        for trans in transactions:
            key_trans = '%s %s' % (trans.location_id.name, trans.unit_id.name)

            if not keyindict(key_trans, location_list):
                location_list[key_trans] = {'location': trans.location_id.name, 'palette': trans.unit_id.name, 'products': {}}
            key_product = '%s - %s - id:%s' % (trans.product_id.product_id.name,
                                               trans.product_id.product_detail if trans.product_id.product_detail else '',
                                               trans.product_id.product_id.id)
            if not key_product in product_metadata:
                if trans.product_id.product_detail:
                    product_name = '%s %s' % (trans.product_id.product_id.name, trans.product_id.product_detail)
                else:
                    product_name = trans.product_id.product_id.name
                product_metadata[key_product] = {
                    'id': trans.product_id.product_id.id,
                    'product': product_name
                }
            if not keyindict(key_product, location_list[key_trans]['products']):
                location_list[key_trans]['products'][key_product] = 0
            location_list[key_trans]['products'][key_product] += trans.qty
            if location_list[key_trans]['products'][key_product] == 0:
                del location_list[key_trans]['products'][key_product]
            if location_list[key_trans]['products'] == {}:
                del location_list[key_trans]

        list_location2 = []
        for key, value in sorted(iter(location_list.items())):
            product = []
            total = 0.00
            for key2, value2 in sorted(iter(value['products'].items())):
                temp = {
                    'location': value['location'],
                    'palette': value['palette'],
                    'product': product_metadata[key2]['product'],
                    'qty':  value2
                }
                product.append(temp)
                total += value2
            temp = {
                'location': value['location'],
                'palette': value['palette'],
                'products': product,
                'gesamt': total
            }
            list_location2.append(temp)

        return {
            'location2': list_location2,
            'date_till': data['form']['date_till']

        }


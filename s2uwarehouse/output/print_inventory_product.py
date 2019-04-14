from odoo import api, models



class PrintInventoryProduct(models.AbstractModel):
    _name = 'report.s2uwarehouse.print_inventory_product'

    @api.model
    def get_report_values(self, docids, data=None):

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        product_list = {}
        product_metadata = {}

        trans = trans_obj.search([('transaction_date', '<=', data['form']['date_till'])], order='product_id asc')

        for line in trans:

            key_trans = '%s - %s - id:%s' % (line.product_id.product_id.name,
                                          line.product_id.product_detail if line.product_id.product_detail else '',
                                          line.product_id.product_id.id)

            location = line.location_id.name

            if key_trans not in product_list:

                product_list[key_trans] = {}
                if line.product_id.product_detail:
                    product_name = '%s %s' % (line.product_id.product_id.name, line.product_id.product_detail)
                else:
                    product_name = line.product_id.product_id.name

                product_metadata[key_trans] = {
                    'id': line.product_id.product_id.id,
                    'product': product_name
                }

            if location not in product_list[key_trans]:
                product_list[key_trans][location] = {}
                product_list[key_trans][location]['qty'] = 0
                product_list[key_trans][location]['price'] = 0
            product_list[key_trans][location]['qty'] = product_list[key_trans][location]['qty'] + line.qty
            product_list[key_trans][location]['price'] = product_list[key_trans][location]['price'] + (line.qty * line.product_id.product_value)
            if product_list[key_trans][location]['qty'] == 0:
                del product_list[key_trans][location]

        list_products2 = []
        for key, value in sorted(iter(product_list.items())):
            location = []
            gesamt = 0.00
            gesamt_p = 0.00
            temp_p = {}
            for key2, value2 in iter(value.items()):
                temp_l = {}
                temp_l['product'] = product_metadata[key]['product']
                temp_l['location'] = key2
                temp_l['qty'] = value2['qty']
                temp_l['price'] = "%.2f" % value2['price']
                location.append(temp_l)
                gesamt += value2['qty']
                gesamt_p += value2['price']
            temp_p['product'] = product_metadata[key]['product']
            temp_p['locations'] = location
            temp_p['gesamt'] = gesamt
            temp_p['gesamt_preis'] = "%.2f" % gesamt_p
            list_products2.append(temp_p)

        return {
            'products2': list_products2,
            'date_till': data['form']['date_till']

        }


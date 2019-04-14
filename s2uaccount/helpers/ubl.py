import sys
from lxml import etree


class UBLHeader(object):
    def __init__(self):
        self.fieldStack = []
        self.currentSubFieldAttrib = False
        self.currentField = False
        self.currentSubField = False
        self.headerFields = ['Invoice.UBLVersionID',
                             'Invoice.ID',
                             'Invoice.IssueDate',
                             'Invoice.InvoiceTypeCode',
                             'Invoice.DocumentCurrencyCode']
        self.headerData = dict.fromkeys(self.headerFields, False)

    def clear_namespace(self, tag):

        try:
            if tag and tag[0] == '{':
                tag = tag.split('}')
                return tag[1]
            return tag
        except:
            return tag

    def validField(self):

        fieldPath = '.'.join(self.fieldStack)
        if fieldPath in self.headerFields:
            return fieldPath
        else:
            return False

    def start(self, tag, attrib):

        tag = self.clear_namespace(tag)
        self.fieldStack.append(tag)
        if type(attrib) == dict:
            self.currentSubFieldAttrib = attrib
        else:
            self.currentSubFieldAttrib = False

    def end(self, tag):

        tag = self.clear_namespace(tag)
        self.fieldStack.pop()

    def data(self, data):
        if self.validField() and data:
            data = data.replace('\t', '')
            data = data.replace('\n', '')
            self.headerData[self.validField()] = data
            if self.currentSubFieldAttrib:
                for k, v in iter(self.currentSubFieldAttrib.items()):
                    self.headerData['%s.%s' % (self.validField(), k)] = v

    def comment(self, text):
        pass

    def close(self):

        return self.headerData


class UBLAccountingParty(object):
    def __init__(self, partyTag):
        self.partyTag = partyTag
        self.setData = 0
        self.currentField = False
        self.currentSubField = False
        self.currentSubFieldAttrib = False
        self.partyFields = ['PartyIdentification', 'PartyName', 'PostalAddress', 'PhysicalLocation', 'PartyTaxScheme',
                            'PartyLegalEntity', 'Contact']
        self.partyData = dict.fromkeys(self.partyFields, False)

    def clear_namespace(self, tag):

        try:
            if tag and tag[0] == '{':
                tag = tag.split('}')
                return tag[1]
            return tag
        except:
            return tag

    def start(self, tag, attrib):

        tag = self.clear_namespace(tag)
        if tag == self.partyTag and self.setData == 0:
            self.setData += 1
        elif tag == 'Party' and self.setData == 1:
            self.setData += 1
        elif self.setData == 2 and tag in self.partyFields:
            self.currentField = tag
            self.setData += 1
        elif self.setData == 3:
            self.currentSubField = tag
            self.setData += 1
            if type(attrib) == dict:
                self.currentSubFieldAttrib = attrib


    def end(self, tag):

        self.currentSubFieldAttrib = False
        tag = self.clear_namespace(tag)
        if tag == self.partyTag and self.setData == 1:
            self.setData -= 1
        elif tag == 'Party' and self.setData == 2:
            self.setData -= 1
        elif self.setData == 3 and tag in self.partyFields:
            self.currentField = False
            self.setData -= 1
        elif self.setData == 4:
            self.currentSubField = False
            self.setData -= 1

    def data(self, data):
        if self.currentField and self.currentSubField and data:
            if not self.partyData[self.currentField]:
                self.partyData[self.currentField] = {}
            data = data.replace('\t', '')
            data = data.replace('\n', '')
            self.partyData[self.currentField][self.currentSubField] = data
            if self.currentSubFieldAttrib:
                for k, v in iter(self.currentSubFieldAttrib.items()):
                    self.partyData[self.currentField]['%s.%s' % (self.currentSubField, k)] = v

    def comment(self, text):
        pass

    def close(self):

        return self.partyData


class UBLTaxTotal(object):
    def __init__(self):
        self.fieldStack = []
        self.currentSubFieldAttrib = False
        self.currentField = False
        self.currentSubField = False
        self.taxFields = ['Invoice.TaxTotal.TaxAmount', 'Invoice.TaxTotal.TaxSubtotal.TaxableAmount',
                          'Invoice.TaxTotal.TaxSubtotal.TaxAmount', 'Invoice.TaxTotal.TaxSubtotal.Percent',
                          'Invoice.TaxTotal.TaxSubtotal.TaxCategory.Percent',
                          'Invoice.TaxTotal.TaxSubtotal.TaxCategory.TaxScheme']
        self.taxData = dict.fromkeys(self.taxFields, False)

    def clear_namespace(self, tag):

        try:
            if tag and tag[0] == '{':
                tag = tag.split('}')
                return tag[1]
            return tag
        except:
            return tag

    def validField(self):

        fieldPath = '.'.join(self.fieldStack)
        if fieldPath in self.taxFields:
            return fieldPath
        else:
            return False

    def start(self, tag, attrib):

        tag = self.clear_namespace(tag)
        self.fieldStack.append(tag)
        if type(attrib) == dict:
            self.currentSubFieldAttrib = attrib
        else:
            self.currentSubFieldAttrib = False

    def end(self, tag):

        tag = self.clear_namespace(tag)
        self.fieldStack.pop()

    def data(self, data):
        if self.validField() and data:
            data = data.replace('\t', '')
            data = data.replace('\n', '')
            self.taxData[self.validField()] = data
            if self.currentSubFieldAttrib:
                for k, v in iter(self.currentSubFieldAttrib.items()):
                    self.taxData['%s.%s' % (self.validField(), k)] = v

    def comment(self, text):
        pass

    def close(self):

        return self.taxData


class LegalMonetaryTotal(object):

    def __init__(self):
        self.fieldStack = []
        self.currentSubFieldAttrib = False
        self.currentField = False
        self.currentSubField = False
        self.monetaryFields = ['Invoice.LegalMonetaryTotal.LineExtensionAmount',
                               'Invoice.LegalMonetaryTotal.TaxExclusiveAmount',
                               'Invoice.LegalMonetaryTotal.TaxInclusiveAmount',
                               'Invoice.LegalMonetaryTotal.PayableAmount']
        self.monetaryData = dict.fromkeys(self.monetaryFields, False)

    def clear_namespace(self, tag):

        try:
            if tag and tag[0] == '{':
                tag = tag.split('}')
                return tag[1]
            return tag
        except:
            return tag

    def validField(self):

        fieldPath = '.'.join(self.fieldStack)
        if fieldPath in self.monetaryFields:
            return fieldPath
        else:
            return False

    def start(self, tag, attrib):

        tag = self.clear_namespace(tag)
        self.fieldStack.append(tag)
        if type(attrib) == dict:
            self.currentSubFieldAttrib = attrib
        else:
            self.currentSubFieldAttrib = False

    def end(self, tag):

        tag = self.clear_namespace(tag)
        self.fieldStack.pop()

    def data(self, data):
        if self.validField() and data:
            data = data.replace('\t', '')
            data = data.replace('\n', '')
            self.monetaryData[self.validField()] = data
            if self.currentSubFieldAttrib:
                for k, v in iter(self.currentSubFieldAttrib.items()):
                    self.monetaryData['%s.%s' % (self.validField(), k)] = v

    def comment(self, text):
        pass

    def close(self):

        return self.monetaryData


class InvoiceLines(object):
    def __init__(self):
        self.fieldStack = []
        self.currentSubFieldAttrib = False
        self.currentField = False
        self.currentSubField = False
        self.lineFields = ['Invoice.InvoiceLine.ID',
                           'Invoice.InvoiceLine.Note',
                           'Invoice.InvoiceLine.InvoicedQuantity',
                           'Invoice.InvoiceLine.LineExtensionAmount',
                           'Invoice.InvoiceLine.TaxTotal.TaxAmount',
                           'Invoice.InvoiceLine.TaxTotal.TaxSubtotal.TaxableAmount',
                           'Invoice.InvoiceLine.TaxTotal.TaxSubtotal.TaxAmount',
                           'Invoice.InvoiceLine.TaxTotal.TaxSubtotal.Percent',
                           'Invoice.InvoiceLine.TaxTotal.TaxCategory.Percent',
                           'Invoice.InvoiceLine.TaxTotal.TaxCategory.TaxScheme.Name',
                           'Invoice.InvoiceLine.Item.Description',
                           'Invoice.InvoiceLine.Item.Name',
                           'Invoice.InvoiceLine.Item.ClassifiedTaxCategory.Percent',
                           'Invoice.InvoiceLine.Item.ClassifiedTaxCategory.TaxScheme',
                           'Invoice.InvoiceLine.Item.Price.PriceAmount']
        self.lineData = dict.fromkeys(self.lineFields, False)
        self.invoiceLines = []

    def clear_namespace(self, tag):

        try:
            if tag and tag[0] == '{':
                tag = tag.split('}')
                return tag[1]
            return tag
        except:
            return tag

    def validField(self):

        fieldPath = '.'.join(self.fieldStack)
        if fieldPath in self.lineFields:
            return fieldPath
        else:
            return False

    def start(self, tag, attrib):

        tag = self.clear_namespace(tag)
        self.fieldStack.append(tag)
        if type(attrib) == dict:
            self.currentSubFieldAttrib = attrib
        else:
            self.currentSubFieldAttrib = False

    def end(self, tag):

        tag = self.clear_namespace(tag)
        if tag == 'InvoiceLine':
            self.invoiceLines.append(self.lineData)
            self.lineData = dict.fromkeys(self.lineFields, False)
        self.fieldStack.pop()

    def data(self, data):
        if self.validField() and data:
            data = data.replace('\t', '')
            data = data.replace('\n', '')
            self.lineData[self.validField()] = data
            if self.currentSubFieldAttrib:
                for k, v in iter(self.currentSubFieldAttrib.items()):
                    self.lineData['%s.%s' % (self.validField(), k)] = v

    def comment(self, text):
        pass

    def close(self):

        return self.invoiceLines


class UBLParser(object):

    def is_ubl(self, xml, input_type="file"):

        try:
            parser = etree.XMLParser(target=UBLHeader())
            if input_type == 'file':
                data = etree.parse(xml, parser)
            else:
                data = etree.fromstring(xml, parser)
            if data['Invoice.UBLVersionID'] != '2.0':
                return False
            return True
        except:
            return False

    def parse_ubl_data(self, xml, input_type="file"):

        parser = etree.XMLParser(target=UBLHeader())
        if input_type == 'file':
            headerData = etree.parse(xml, parser)
        else:
            headerData = etree.fromstring(xml, parser)
        if headerData['Invoice.UBLVersionID'] != '2.0':
            raise ValueError('Only UBL version 2.0 is supported.')

        parser = etree.XMLParser(target=UBLAccountingParty('AccountingSupplierParty'))
        if input_type == 'file':
            supplierData = etree.parse(xml, parser)
        else:
            supplierData = etree.fromstring(xml, parser)

        parser = etree.XMLParser(target=UBLAccountingParty('AccountingCustomerParty'))
        if input_type == 'file':
            customerData = etree.parse(xml, parser)
        else:
            customerData = etree.fromstring(xml, parser)

        parser = etree.XMLParser(target=UBLTaxTotal())
        if input_type == 'file':
            taxData = etree.parse(xml, parser)
        else:
            taxData = etree.fromstring(xml, parser)

        parser = etree.XMLParser(target=LegalMonetaryTotal())
        if input_type == 'file':
            monetaryData = etree.parse(xml, parser)
        else:
            monetaryData = etree.fromstring(xml, parser)

        parser = etree.XMLParser(target=InvoiceLines())
        if input_type == 'file':
            linesData = etree.parse(xml, parser)
        else:
            linesData = etree.fromstring(xml, parser)

        return headerData, supplierData, customerData, taxData, monetaryData, linesData


def main(args):
    if len(args) > 1:
        ublfile = args[1]
    else:
        ublfile = 'C:/Users/b.ubbels/Dropbox/Business/clients/PBBZ/test-bestanden/ubl/test1.xml'

    ubl = UBLParser()
    ubl.parse_ubl_data(ublfile)

    print("parsing ubl file [%s] ..." % ublfile)
    print("done.")

if __name__ == '__main__':
    main(sys.argv)

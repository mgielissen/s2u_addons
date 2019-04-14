# -*- coding: utf-8 -*-

import base64
import hashlib
import itertools
import logging
import mimetypes
import os
import os.path
import re
from collections import defaultdict
import uuid

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import config, human_size, ustr, html_escape
from odoo import api, fields, models, _, tools


_logger = logging.getLogger(__name__)


class S2uDocumentTypeExt(models.Model):
    _name = "s2u.document.type.ext"
    _description = "Document types extensions"
    _order = "name"

    name = fields.Char(string='Extension', required=True, index=True)
    doctype_id = fields.Many2one('s2u.document.type', string='Doc. type', ondelete='cascade')


class S2uDocumentType(models.Model):
    _name = "s2u.document.type"
    _description = "Document types"
    _order = "name"

    name = fields.Char(string='Doc. type', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    extension_ids = fields.One2many('s2u.document.type.ext', 'doctype_id',
                                    string='Extensions')


class S2uDocument(models.Model):
    _name = 's2u.document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    @api.model
    def _storage(self):
        return self.env['ir.config_parameter'].sudo().get_param('ir_attachment.location', 'file')

    @api.model
    def _filestore(self):
        return config.filestore(self._cr.dbname)

    @api.model
    def force_storage(self):
        """Force all attachments to be stored in the currently configured storage"""
        if not self.env.user._is_admin():
            raise AccessError(_('Only administrators can execute this action.'))

        # domain to retrieve the attachments to migrate
        domain = {
            'db': [('store_fname', '!=', False)],
            'file': [('db_datas', '!=', False)],
        }[self._storage()]

        for attach in self.search(domain):
            attach.write({'datas': attach.datas})
        return True

    @api.model
    def _full_path(self, path):
        # sanitize path
        path = re.sub('[.]', '', path)
        path = path.strip('/\\')
        return os.path.join(self._filestore(), path)

    @api.model
    def _get_path(self, bin_data, sha):
        # retro compatibility
        fname = sha[:3] + '/' + sha
        full_path = self._full_path(fname)
        if os.path.isfile(full_path):
            return fname, full_path  # keep existing path

        # scatter files across 256 dirs
        # we use '/' in the db (even on windows)
        fname = sha[:2] + '/' + sha
        full_path = self._full_path(fname)
        dirname = os.path.dirname(full_path)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        return fname, full_path

    @api.model
    def _file_read(self, fname, bin_size=False):
        full_path = self._full_path(fname)
        r = ''
        try:
            if bin_size:
                r = human_size(os.path.getsize(full_path))
            else:
                r = base64.b64encode(open(full_path, 'rb').read())
        except (IOError, OSError):
            _logger.info("_read_file reading %s", full_path, exc_info=True)
        return r

    @api.model
    def _file_write(self, value, checksum):
        bin_value = base64.b64decode(value)
        fname, full_path = self._get_path(bin_value, checksum)
        if not os.path.exists(full_path):
            try:
                with open(full_path, 'wb') as fp:
                    fp.write(bin_value)
                # add fname to checklist, in case the transaction aborts
                self._mark_for_gc(fname)
            except IOError:
                _logger.info("_file_write writing %s", full_path, exc_info=True)
        return fname

    @api.model
    def _file_delete(self, fname):
        # simply add fname to checklist, it will be garbage-collected later
        self._mark_for_gc(fname)

    def _mark_for_gc(self, fname):
        """ Add ``fname`` in a checklist for the filestore garbage collection. """
        # we use a spooldir: add an empty file in the subdirectory 'checklist'
        full_path = os.path.join(self._full_path('checklist'), fname)
        if not os.path.exists(full_path):
            dirname = os.path.dirname(full_path)
            if not os.path.isdir(dirname):
                with tools.ignore(OSError):
                    os.makedirs(dirname)
            open(full_path, 'ab').close()

    @api.model
    def _file_gc(self):
        """ Perform the garbage collection of the filestore. """
        if self._storage() != 'file':
            return

        # Continue in a new transaction. The LOCK statement below must be the
        # first one in the current transaction, otherwise the database snapshot
        # used by it may not contain the most recent changes made to the table
        # ir_attachment! Indeed, if concurrent transactions create attachments,
        # the LOCK statement will wait until those concurrent transactions end.
        # But this transaction will not see the new attachements if it has done
        # other requests before the LOCK (like the method _storage() above).
        cr = self._cr
        cr.commit()

        # prevent all concurrent updates on ir_attachment while collecting!
        cr.execute("LOCK ir_attachment IN SHARE MODE")

        # retrieve the file names from the checklist
        checklist = {}
        for dirpath, _, filenames in os.walk(self._full_path('checklist')):
            dirname = os.path.basename(dirpath)
            for filename in filenames:
                fname = "%s/%s" % (dirname, filename)
                checklist[fname] = os.path.join(dirpath, filename)

        # determine which files to keep among the checklist
        whitelist = set()
        for names in cr.split_for_in_conditions(checklist):
            cr.execute("SELECT store_fname FROM ir_attachment WHERE store_fname IN %s", [names])
            whitelist.update(row[0] for row in cr.fetchall())

        # remove garbage files, and clean up checklist
        removed = 0
        for fname, filepath in checklist.items():
            if fname not in whitelist:
                try:
                    os.unlink(self._full_path(fname))
                    removed += 1
                except (OSError, IOError):
                    _logger.info("_file_gc could not unlink %s", self._full_path(fname), exc_info=True)
            with tools.ignore(OSError):
                os.unlink(filepath)

        # commit to release the lock
        cr.commit()
        _logger.info("filestore gc %d checked, %d removed", len(checklist), removed)

    @api.depends('store_fname', 'db_datas')
    def _compute_datas(self):
        bin_size = self._context.get('bin_size')
        for attach in self:
            if attach.store_fname:
                attach.datas = self._file_read(attach.store_fname, bin_size)
            else:
                attach.datas = attach.db_datas

    def _inverse_datas(self):
        location = self._storage()
        for attach in self:
            # compute the fields that depend on datas
            value = attach.datas
            bin_data = base64.b64decode(value) if value else b''
            vals = {
                'file_size': len(bin_data),
                'checksum': self._compute_checksum(bin_data),
                'store_fname': False,
                'db_datas': value,
            }
            if value and location != 'db':
                # save it to the filestore
                vals['store_fname'] = self._file_write(value, vals['checksum'])
                vals['db_datas'] = False

            # take current location in filestore to possibly garbage-collect it
            fname = attach.store_fname
            # write as superuser, as user probably does not have write access
            super(S2uDocument, attach.sudo()).write(vals)
            if fname:
                self._file_delete(fname)

    def _compute_checksum(self, bin_data):
        """ compute the checksum for the given datas
            :param bin_data : datas in its binary form
        """
        # an empty file has a checksum too (for caching)
        return hashlib.sha1(bin_data or b'').hexdigest()

    @api.onchange('name')
    def onchange_name(self):
        if self.name:
            extension = os.path.splitext(self.name)[1][1:]
            unknown_ext = self.env['s2u.document.type.ext'].search([('name', '=', '*.*')], limit=1)
            if extension:
                ext = self.env['s2u.document.type.ext'].search([('name', 'ilike', extension)], limit=1)
                if ext:
                    self.doctype_id = ext.doctype_id.id
                elif unknown_ext:
                    self.doctype_id = unknown_ext.doctype_id.id
            elif unknown_ext:
                self.doctype_id = unknown_ext.doctype_id.id

    @api.multi
    def write(self, vals):
        # remove computed field depending of datas
        for field in ('file_size', 'checksum'):
            vals.pop(field, False)

        if vals.get('datas'):
            fname = self.name
            version = self.doc_version
            stamp = self.doc_stamp
            user = self.user_id.name
            datas = self.datas
            vals['doc_version'] = self.doc_version + 1
            vals['user_id'] = self.env.user.id
            vals['doc_stamp'] = fields.Datetime.now()

        res = super(S2uDocument, self).write(vals)
        if vals.get('datas') and res:
            if datas:
                attachments = [('%s' % fname, base64.b64decode(datas))]
                self.message_post(body='Version %s from %s by %s has been changed. Attached is the old version:'
                                       % (version, stamp, user), subject='', attachments=attachments)

        return res

    @api.multi
    def copy(self, default=None):

        return super(S2uDocument, self).copy(default)

    @api.multi
    def unlink(self):
        # First delete in the database, *then* in the filesystem if the
        # database allowed it. Helps avoid errors when concurrent transactions
        # are deleting the same file, and some of the transactions are
        # rolled back by PostgreSQL (due to concurrent updates detection).
        to_delete = set(attach.store_fname for attach in self if attach.store_fname)
        res = super(S2uDocument, self).unlink()
        for file_path in to_delete:
            self._file_delete(file_path)

        return res

    @api.model
    def create(self, values):
        # remove computed field depending of datas
        for field in ('file_size', 'checksum'):
            values.pop(field, False)
        return super(S2uDocument, self).create(values)

    name = fields.Char('Attachment Name', required=True, index=True)
    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True, ondelete='cascade', index=True)
    description = fields.Text('Description')
    res_model = fields.Char('Resource Model', index=True)
    res_id = fields.Integer('Resource ID', index=True)
    doc_context = fields.Char('Context', index=True, required=True)
    rec_context = fields.Char('Reference', index=True, required=True)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    doc_stamp = fields.Datetime(string='Date/time', index=True, copy=False, default=lambda self: fields.Datetime.now())
    doc_version = fields.Integer(string='Version', default=1, required=True)
    doctype_id = fields.Many2one('s2u.document.type', string='Doc. type', ondelete='restrict', index=True)
    datas = fields.Binary(string='File Content', compute='_compute_datas', inverse='_inverse_datas')
    db_datas = fields.Binary('Database Data')
    store_fname = fields.Char('Stored Filename')
    file_size = fields.Integer('File Size', readonly=True)
    checksum = fields.Char("Checksum/SHA1", size=40, index=True, readonly=True)

from odoo import models, fields, api

class PacienteHistorialClinico(models.Model):
    _name = 'pacientes'
    _description = 'Historial Clínico del Paciente'

    _rec_names_search = ['nom_paciente','ape_paciente', 'dni']
    name = fields.Char(string='Código', readonly=True, copy=False, default='Nuevo')
    
    # datos personales identificadores
    nom_paciente = fields.Char(string='Nombre del Paciente', required=True)
    ape_paciente = fields.Char(string='Apellido del Paciente', required=True)
    fecha_nacimiento = fields.Date(string='Fecha de Nacimiento', required=True)
    edad = fields.Integer(string='Edad', compute='_compute_edad', store=True)
    dni = fields.Char(string='DNI', required=True)

    #datos de comunicacion
    telf_principal = fields.Char(string='Teléfono')
    telf_emergencia = fields.Char(string='Teléfono de Emergencia')
    email = fields.Char(string='Correo Electrónico')
    

    pais=fields.Many2one('res.country', string='País', default=lambda self: self.env['res.country'].search([('code', '=', 'VE')], limit=1))
    estado=fields.Many2one('res.country.state', string='Estado' , domain="[('country_id', '=', pais)]")
    municipio=fields.Char(string='Municipio')
    direccion = fields.Char(string='Dirección')


    #datos medicos
    tratamiento_medico = fields.Boolean(string='Estas en tratamiento medico actualmente?', default=False)
    tipo_tratamiento = fields.Text(string='De que tipo de tratamiento:')
    prop_hemorragia=fields.Boolean(string='Propenso a hemorrajia?' ,default=False)
    alergia_medicamento=fields.Boolean(string='Alergico a algunos medicamentos?', default=False)
    desc_alergia_medicamento=fields.Text(string='Descripción de la alergia')

    problemas_anesteciaBucal=fields.Boolean(string='Problemas con anestesia bucal?', default=False)


    @api.depends('fecha_nacimiento')
    def _compute_edad(self):
        for record in self:
            if record.fecha_nacimiento:
                hoy = fields.Date.today()
                record.edad = hoy.year - record.fecha_nacimiento.year - \
                    ((hoy.month, hoy.day) < (record.fecha_nacimiento.month, record.fecha_nacimiento.day))
            else:
                record.edad = 0
    @api.depends('nom_paciente', 'ape_paciente','dni')
    def _compute_display_name(self):
        for record in self:
            nombre_completo = f"{record.nom_paciente or ''} {record.ape_paciente or ''}".strip()
            record.display_name =  nombre_completo
            # if  self.env.context.get('mostrar_solo_dni'):
            #     record.display_name = record.dni or 'Sin DNI'
            # else:
            #     record.display_name = nombre_completo

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            
            if vals.get('name', 'Nuevo') == 'Nuevo':

                secuencia = self.env['ir.sequence'].next_by_code('pacientes')
                vals['name'] = secuencia or 'Nuevo'
                

        records=super().create(vals_list)

        for record in records:
            nombre_completo = f"{record.nom_paciente} {record.ape_paciente}".strip()
            self.env['res.partner'].create({
                'name': nombre_completo,
                'vat': record.dni,
                'phone': record.telf_principal,
                'email': record.email,
                'street': record.direccion,
                'is_company': False,
                'comment': f"Paciente registrado con el código: {record.name}",
                'es_paciente': True,
            })
        
        return records

class ResPartner(models.Model):
    _inherit = 'res.partner'
    es_paciente = fields.Boolean(string='Es Paciente', default=False)

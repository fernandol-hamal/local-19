from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import datetime
import logging
import re

_logger = logging.getLogger(__name__)

class HistoriaPaciente(models.Model):
    _name = 'historia.paciente'
    _description = 'Historia Clínica'
    
    name = fields.Char(string='Código', readonly=True, copy=False, default='Nuevo')

    # Datos del paciente
    paciente_id = fields.Many2one('pacientes', string='Paciente', required=True)
    CI = fields.Char(string='Cédula de Identidad', related='paciente_id.dni', readonly=True)
    nom_paciente = fields.Char(string='Nombre del Paciente', related='paciente_id.nom_paciente')
    ape_paciente = fields.Char(string='Apellido del Paciente', related='paciente_id.ape_paciente')
    edad = fields.Integer(string='Edad', related='paciente_id.edad')
    telf = fields.Char(string='Teléfono', related='paciente_id.telf_principal')
    email = fields.Char(string='Correo Electrónico', related='paciente_id.email')
    
    # Alertas Médicas
    trat_medico = fields.Boolean(string='Tratamiento médico actual', related='paciente_id.tratamiento_medico')
    tipo_tratamiento = fields.Text(string='Tipo de tratamiento', related='paciente_id.tipo_tratamiento')
    prop_hemorragia = fields.Boolean(string='Propenso a hemorragia', related='paciente_id.prop_hemorragia')
    alergia_medicamento = fields.Boolean(string='Alérgico a medicamentos', related='paciente_id.alergia_medicamento')
    desc_alergia_medicamento = fields.Text(string='Descripción alergia', related='paciente_id.desc_alergia_medicamento')
    problemas_anesteciaBucal = fields.Boolean(string='Problemas anestesia', related='paciente_id.problemas_anesteciaBucal')

    # Datos de la consulta
    tipServ = fields.Selection(selection=[
        ('general', 'Odontología General'),
        ('ortodoncia', 'Ortodoncia (Brackets y Alineadores)'),
        ('endodoncia', 'Endodoncia (Tratamiento de Conducto)'),
        ('periodoncia', 'Periodoncia (Encías)'),
        ('odontopediatria', 'Odontopediatría (Niños)'),
        ('cirugia', 'Cirugía Oral y Maxilofacial'),
        ('implantologia', 'Implantología (Implantes Dentales)'),
        ('prostodoncia', 'Prostodoncia / Rehabilitación Oral (Prótesis)'),
        ('estetica', 'Odontología Estética / Cosmética'),
        ('diagnostico', 'Diagnóstico y Radiología'),
    ], string='Especialidad', required=True, default='general')
    
    consultorio = fields.Integer(string='Consultorio', required=True)
    fechaHistoria = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    motivo = fields.Char(string='Motivo', required=False)
    
    # --- CAMPO DONDE SE GUARDARÁ EL AUDIO DEL BOTON ---
    audio_file = fields.Binary(string='Audio de Consulta', attachment=True)
    
    examenHecho = fields.Text(string='Evaluación Médica realizada')

    tratamiento_ids = fields.One2many('tratamiento.historia', 'historia_id', string='Tratamientos')
    odontograma_line_ids = fields.One2many('odontograma.linea', 'historia_id', string='Líneas del Odontograma')

    @api.model_create_multi  
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('historia.paciente') or 'Nuevo'
        return super(HistoriaPaciente, self).create(vals_list)

    def action_completar_con_ia(self):
        self.ensure_one()
        
        if not self.examenHecho and not self.audio_file:
            raise UserError("Grabe un audio o escriba la evaluación médica antes de continuar.")

        api_key = self.env['ir.config_parameter'].sudo().get_param('gemini.api_key')
        if not api_key:
            raise UserError("Falta la clave 'gemini.api_key' en Parámetros del Sistema.")

        model_id = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        
        valid_services = [opt[0] for opt in self._fields['tipServ'].selection]
        
        prompt = f"""Analiza la siguiente evaluación médica odontológica. 
        Si recibes un audio, escúchalo, transcríbelo y extrae la información clínica.
        Responde exclusivamente con un JSON plano con la siguiente estructura (NO AGREGUES MARKDOWN NI TEXTO ADICIONAL): 
        {{"tipServ": "uno de: {valid_services}", "motivo": "resumen corto", "fechaHistoria": "YYYY-MM-DD", "consultorio": "numero", "examenHecho": "Transcripción exacta del audio o resumen detallado"}}.
        Hoy es {datetime.date.today()}."""

        parts = [{"text": prompt}]

        if self.examenHecho:
            parts.append({"text": f"Texto adicional proporcionado: '{self.examenHecho}'"})

        if self.audio_file:
            audio_b64 = self.audio_file.decode('utf-8') if isinstance(self.audio_file, bytes) else self.audio_file
            # El navegador graba en webm por defecto
            parts.append({
                "inline_data": {
                    "mime_type": "audio/webm",
                    "data": audio_b64
                }
            })

        try:
            payload = {"contents":[{"parts": parts}]}
            response = requests.post(url, json=payload, timeout=30) 
            
            if response.status_code == 404:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                response = requests.post(url, json=payload, timeout=30)

            if response.status_code != 200:
                raise UserError(f"Error AI ({response.status_code}): {response.text}")

            result = response.json()
            ia_text = result['candidates'][0]['content']['parts'][0]['text']
            
            match = re.search(r'\{.*\}', ia_text, re.DOTALL)
            if not match:
                raise UserError("La IA no devolvió un formato JSON válido.")
            
            data = json.loads(match.group())
            vals = {}
            if data.get('tipServ') in valid_services: vals['tipServ'] = data['tipServ']
            if data.get('motivo'): vals['motivo'] = data['motivo']
            if data.get('fechaHistoria'): vals['fechaHistoria'] = data['fechaHistoria']
            if data.get('consultorio'):
                try: 
                    num = ''.join(filter(str.isdigit, str(data['consultorio'])))
                    if num: vals['consultorio'] = int(num)
                except: pass
            
            if data.get('examenHecho'):
                vals['examenHecho'] = data['examenHecho']
            
            if vals:
                self.write(vals)
            return True

        except Exception as e:
            raise UserError(f"Error técnico: {str(e)}")

class TratamientoHistoria(models.Model):
    _name = 'tratamiento.historia'
    _description = 'Sesiones de Tratamiento'
    historia_id = fields.Many2one('historia.paciente', string='Paciente', ondelete='cascade')
    sesion = fields.Integer(string='Sesión')
    fecha = fields.Date(string='Fecha', default=fields.Date.context_today)
    tratamiento = fields.Text(string='Tratamiento')

class OdontogramaLinea(models.Model):
    _name = 'odontograma.linea'
    _description = 'Línea de Detalle de Odontograma'
    historia_id = fields.Many2one('historia.paciente', ondelete='cascade')
    diente_numero = fields.Integer(string='Diente')
    procedimiento = fields.Selection([
        ('caries', 'Pintar Caras'), ('corona', 'Corona'), ('perno', 'Perno'),
        ('rx', 'Rayos X'), ('endodoncia', 'Endodoncia'), ('implante', 'Implante'),
        ('ausente', 'Pieza Ausente'), ('sellante', 'Sellante'), ('soportes', 'Soportes'),
        ('otro', 'Otro...'),
    ], string='Procedimiento')
    cara = fields.Selection([
        ('c1', 'Superior'), ('c2', 'Derecha'), ('c3', 'Inferior'), 
        ('c4', 'Izquierda'), ('c5', 'Centro')
    ], string='Ubicación')
    notas = fields.Text(string='Notas')


class ClinicaDashBorard(models.Model):
    _name = 'clinica.dashboard'
    _description = 'Menu Principal de la Clínica'
    name = fields.Char(default='Dashboard')
    def dummy_method(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Aviso', 'message': 'Función en desarrollo.', 'type': 'info'}
        }
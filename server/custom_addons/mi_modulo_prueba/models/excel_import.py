import io
import base64
from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError
import openpyxl
from datetime import datetime

class ExcelTimesheetImport(models.TransientModel):
    _name = 'excel.timesheet.import'
    _description = 'Importador de Excel Jira con IDs Únicos'

    excel_file = fields.Binary(string="Archivo Excel", required=True)
    file_name = fields.Char(string="Nombre del archivo")

    def action_import_excel(self):
        if not self.excel_file:
            raise UserError(_("Por favor, suba un archivo."))

        file_data = base64.b64decode(self.excel_file)
        f = io.BytesIO(file_data)
        
        try:
            workbook = openpyxl.load_workbook(f, data_only=True)
            sheet = workbook.active
        except Exception as e:
            raise UserError(_("Error al leer el Excel: %s") % str(e))

        creados = 0
        actualizados = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):
            # MAPEO DE COLUMNAS (Basado en image_a60fcf.png):
            # row[0] = Worklog Id (A) -> Usado para x_jira_worklog_id
            # row[1] = Issue Key (B)  -> Usado para x_jira_key
            # row[2] = Issue Summary (C)
            # row[5] = Time Spent Sec (F)
            # row[6] = Start Date (G)
            # row[8] = Comment (I)
            # row[9] = Author (J)
            # row[11] = Project Key (L) -> Usado para x_jira_id (ID único del proyecto)
            # row[12] = Project Name (M)
            
            worklog_id = str(row[0]) if row[0] else False
            jira_project_id = str(row[11]) if row[11] else False # Project Key como ID único
            jira_task_key = str(row[1]) if row[1] else False    # Issue Key (KAN-1) como ID único

            if not worklog_id or not jira_project_id:
                continue

            # 1. GESTIÓN DE PROYECTO (Búsqueda por x_jira_id)
            project = self.env['project.project'].search([('x_jira_id', '=', jira_project_id)], limit=1)
            
            if project:
                # Si existe, actualizamos el nombre por si cambió en Jira
                if project.name != str(row[12]):
                    project.write({'name': str(row[12])})
            else:
                # Si no existe, lo creamos con su ID único
                project = self.env['project.project'].create({
                    'name': str(row[12]),
                    'x_jira_id': jira_project_id,
                    'allow_timesheets': True,
                })

            # 2. GESTIÓN DE TAREA (Búsqueda por x_jira_key)
            task = self.env['project.task'].search([
                ('x_jira_key', '=', jira_task_key),
                ('project_id', '=', project.id)
            ], limit=1)

            task_name = f"[{jira_task_key}] {str(row[2])}"
            if task:
                # Actualizamos el nombre si cambió el resumen en Jira
                if task.name != task_name:
                    task.write({'name': task_name})
            else:
                # Creamos la tarea vinculada a su ID único
                task = self.env['project.task'].create({
                    'name': task_name,
                    'x_jira_key': jira_task_key,
                    'project_id': project.id,
                })

            # 3. GESTIÓN DE EMPLEADO Y DATOS DE HORA
            author_name = str(row[9]).strip() if row[9] else False
            comment = str(row[8]) if row[8] else '/'
            hours = float(row[5] or 0.0) / 3600.0 
            
            try:
                date_str = str(row[6])[:10]
                date_val = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                date_val = fields.Date.today()

            employee = self.env['hr.employee'].search([('name', '=', author_name)], limit=1)
            target_employee_id = employee.id if employee else self.env.user.employee_id.id

            # 4. GESTIÓN DEL PARTE DE HORAS (Upsert)
            existing_line = self.env['account.analytic.line'].search([
                ('x_jira_worklog_id', '=', worklog_id)
            ], limit=1)

            if existing_line:
                has_changes = False
                if (existing_line.name != comment or 
                    not tools.float_is_zero(existing_line.unit_amount - hours, precision_digits=2) or
                    existing_line.employee_id.id != target_employee_id or
                    existing_line.task_id.id != task.id):
                    has_changes = True
                
                if has_changes:
                    existing_line.write({
                        'name': comment,
                        'unit_amount': hours,
                        'date': date_val,
                        'employee_id': target_employee_id,
                        'project_id': project.id,
                        'task_id': task.id,
                    })
                    actualizados += 1
            else:
                self.env['account.analytic.line'].create({
                    'x_jira_worklog_id': worklog_id,
                    'name': comment,
                    'project_id': project.id,
                    'task_id': task.id,
                    'unit_amount': hours,
                    'date': date_val,
                    'employee_id': target_employee_id,
                })
                creados += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sincronización Exitosa'),
                'message': _('Proyectos y Tareas actualizados. Creados: %s | Actualizados: %s') % (creados, actualizados),
                'type': 'success',
            }
        }
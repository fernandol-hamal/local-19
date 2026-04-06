from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
from requests.auth import HTTPBasicAuth
import json

class ProjectProject(models.Model):
    _inherit = 'project.project'
    # Ahora guardará el Project Key (ej: 'KAN')
    x_jira_id = fields.Char(string='Project Key de Jira', copy=False, index=True)

class ProjectTask(models.Model):
    _inherit = 'project.task'
    x_jira_key = fields.Char(string='Key de Jira', copy=False, index=True)

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    x_jira_worklog_id = fields.Char(string='ID de Worklog Jira', copy=False, index=True)

class JiraSynchro(models.TransientModel):
    _name = 'jira.synchro'
    _description = 'Sincronización manual de Jira'
    
    start_date = fields.Date(string='Fecha Inicio', required=True, default=fields.Date.context_today)
    end_date = fields.Date(string='Fecha Fin', required=True, default=fields.Date.context_today)
    jira_url = fields.Char(string='URL de Jira', required=True, default='https://hamalsolutions.atlassian.net')
    jira_email = fields.Char(string='Correo de Jira', required=True)
    jira_api_token = fields.Char(string='API Token de Jira', required=True)

    def action_sync_jira(self):
        self.ensure_one()
        start_str = self.start_date.strftime('%Y-%m-%d')
        end_str = self.end_date.strftime('%Y-%m-%d')
        
        base_url = self.jira_url.strip().rstrip('/')
        auth = HTTPBasicAuth(self.jira_email.strip(), self.jira_api_token.strip())
        headers = {
            "Accept": "application/json", 
            "Content-Type": "application/json",
            "X-Atlassian-Token": "no-check"
        }

        url_search = f"{base_url}/rest/api/3/search/jql"
        payload = {
            "jql": "timespent > 0 ORDER BY updated DESC",
            "fields": ["project", "summary"],
            "maxResults": 100
        }

        try:
            response = requests.post(url_search, headers=headers, auth=auth, json=payload, timeout=60)
            if response.status_code != 200:
                raise UserError(f"Error Jira: {response.text}")
            issues = response.json().get('issues', [])
        except Exception as e:
            raise UserError(f"Error de conexión: {str(e)}")

        horas_creadas = 0
        horas_actualizadas = 0
        cambios_estructura = 0 
        total_issues_procesados = 0

        for issue in issues:
            if not isinstance(issue, dict) or 'key' not in issue:
                continue

            total_issues_procesados += 1
            task_key = issue['key']
            f = issue.get('fields', {})
            jira_project_data = f.get('project', {})
            
            # --- CAMBIO AQUÍ: Usamos 'key' en lugar de 'id' ---
            jira_project_key = jira_project_data.get('key') # Ej: 'KAN'
            jira_project_name = jira_project_data.get('name')
            jira_task_summary = f"[{task_key}] {f.get('summary', 'Sin título')}"
            
            # --- 1. SINCRONIZACIÓN DE PROYECTO (Por Key) ---
            project = self.env['project.project'].search([('x_jira_id', '=', jira_project_key)], limit=1)
            if project:
                if project.name != jira_project_name:
                    project.write({'name': jira_project_name})
                    cambios_estructura += 1
            else:
                project = self.env['project.project'].create({
                    'name': jira_project_name, 
                    'x_jira_id': jira_project_key
                })

            # --- 2. SINCRONIZACIÓN DE TAREA ---
            task = self.env['project.task'].search([('x_jira_key', '=', task_key)], limit=1)
            if task:
                if task.name != jira_task_summary or task.project_id != project:
                    task.write({
                        'name': jira_task_summary,
                        'project_id': project.id
                    })
                    cambios_estructura += 1
            else:
                task = self.env['project.task'].create({
                    'name': jira_task_summary,
                    'project_id': project.id,
                    'x_jira_key': task_key
                })

            # --- 3. PROCESAMIENTO DE WORKLOGS ---
            url_wl = f"{base_url}/rest/api/3/issue/{task_key}/worklog"
            try:
                res_wl = requests.get(url_wl, headers=headers, auth=auth, timeout=30)
                if res_wl.status_code == 200:
                    for wl in res_wl.json().get('worklogs', []):
                        wl_date = wl['started'][:10]
                        
                        if start_str <= wl_date <= end_str:
                            email = wl.get('author', {}).get('emailAddress')
                            employee = self.env['hr.employee'].search([('work_email', '=', email)], limit=1)
                            
                            if employee:
                                w_id = str(wl['id'])
                                new_duration = wl['timeSpentSeconds'] / 3600.0
                                
                                # Extraer Comentario (ADF a Texto)
                                jira_comment = f"Jira: {task_key}"
                                raw_comment = wl.get('comment')
                                if isinstance(raw_comment, dict):
                                    try:
                                        text_parts = []
                                        for block in raw_comment.get('content', []):
                                            for item in block.get('content', []):
                                                if item.get('type') == 'text':
                                                    text_parts.append(item.get('text', ''))
                                        if text_parts: jira_comment = " ".join(text_parts)
                                    except: pass
                                elif isinstance(raw_comment, str) and raw_comment:
                                    jira_comment = raw_comment

                                # Actualizar o Crear Línea Analítica
                                existing_line = self.env['account.analytic.line'].search([
                                    ('x_jira_worklog_id', '=', w_id)
                                ], limit=1)

                                if existing_line:
                                    if (existing_line.unit_amount != new_duration or 
                                        existing_line.name != jira_comment or
                                        existing_line.task_id != task or
                                        existing_line.date != wl_date):
                                        existing_line.write({
                                            'name': jira_comment,
                                            'unit_amount': new_duration,
                                            'date': wl_date,
                                            'task_id': task.id,
                                            'project_id': project.id
                                        })
                                        horas_actualizadas += 1
                                else:
                                    self.env['account.analytic.line'].create({
                                        'name': jira_comment,
                                        'project_id': project.id,
                                        'task_id': task.id,
                                        'employee_id': employee.id,
                                        'date': wl_date,
                                        'unit_amount': new_duration,
                                        'x_jira_worklog_id': w_id
                                    })
                                    horas_creadas += 1
            except:
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sincronización Global Finalizada',
                'message': f'Nuevas: {horas_creadas} | Actualizadas: {horas_actualizadas} | Cambios Estructura: {cambios_estructura}',
                'type': 'success',
                'sticky': False,
            }
        }
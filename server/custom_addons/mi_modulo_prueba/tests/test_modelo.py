from odoo.tests.common import TransactionCase
from odoo.fields import Date

class TestPruebaModelo(TransactionCase):

    def setUp(self):
        """Preparamos los datos para las pruebas"""
        super(TestPruebaModelo, self).setUp()

        self.paciente_test = self.env['pacientes'].create({
            'nom_paciente': 'Juan',
            'ape_paciente': 'Pérez',
            'fecha_nacimiento': Date.today(),
            'dni': 'V-12345678'
        })

        self.test_record = self.env['historia.paciente'].create({
            'paciente_id': self.paciente_test.id,
            'tipServ': 'general',
            'consultorio': 1,
            'fechaHistoria': Date.today(),
            'motivo': 'Limpieza de rutina',
        })

    def test_creacion_registro(self):
        """Verificar que el registro principal se creó y los datos se autocompletaron"""
      
        self.assertTrue(self.test_record.id, "El registro de historia clínica no se creó.")
        
     
        self.assertEqual(self.test_record.tipServ, 'general')
        
   
        self.assertEqual(self.test_record.CI, 'V-12345678', "El campo CI no se autocompletó correctamente.")
        
 
        self.assertEqual(self.test_record.paciente_id.nom_paciente, 'Juan')
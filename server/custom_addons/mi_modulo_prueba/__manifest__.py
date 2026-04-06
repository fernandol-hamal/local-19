# __manifest__.py
{
    'name': 'History Of patients',
    'version': '1.0',
    'author': 'Hammal Solutions',
    # CAMBIO AQUÍ: Agregamos 'web'
    'depends': ['base', 'web','iap','mail'], 
    'assets': {
        'web.assets_backend': [
            'mi_modulo_prueba/static/src/css/odontograma.css',
            'mi_modulo_prueba/static/src/js/odontograma_widget.js',
            'mi_modulo_prueba/static/src/xml/odontograma_template.xml',
            'mi_modulo_prueba/static/src/css/audio_recorder.css',
            'mi_modulo_prueba/static/src/js/audio_recorder.js',
            'mi_modulo_prueba/static/src/xml/audio_recorder.xml',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/odontograma_view.xml',
        'views/pacientesView.xml',
        'views/views.xml',
        'data/data.xml',
        'data/estadosVenezuela.xml',
        'views/principalMenuView.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
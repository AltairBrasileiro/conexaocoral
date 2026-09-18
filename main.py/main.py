from nicegui import ui

# Estilização da página
ui.colors(primary='#D32F2F', secondary='#000000', accent='#FFFFFF')

# Cabeçalho / Título
with ui.column().classes('w-full items-center justify-center my-6'):
    ui.label('Consulado CoralJampa').classes('text-4xl font-bold text-red-700')
    ui.label('Torcida Tricolor em João Pessoa - PB').classes('text-lg text-gray-600')

# Conteúdo Principal
with ui.card().classes('w-full max-w-2xl mx-auto p-6'):
    ui.label('Bem-vindo ao Consulado!').classes('text-xl font-bold mb-2')
    ui.label('Acompanhe as reuniões, eventos e transmissões de jogos conosco.')

    ui.separator().classes('my-4')

    # Formulário
    ui.label('Faça seu cadastro:').classes('font-semibold')
    nome_input = ui.input('Nome Completo').classes('w-full')
    phone_input = ui.input('WhatsApp').classes('w-full')

    def cadastrar():
        if nome_input.value:
            ui.notify(f'Bem-vindo ao Conexão Coral, {nome_input.value}!', type='positive')
        else:
            ui.notify('Por favor, digite seu nome.', type='warning')

    ui.button('Cadastrar', on_click=cadastrar).classes('mt-4 text-white bg-red-700')

# Rodapé
with ui.footer().classes('bg-black text-white justify-center'):
    ui.label('Consulado CoralJampa © João Pessoa')

# Executar aplicação
ui.run(title='Consulado CoralJampa')
"""Classificação de chamados de suporte (português do Brasil).

Empresa fictícia *Ipê Labs*: vende o app por assinatura Ipê Cloud (planos
Básico → Empresarial) e aparelhos de casa inteligente entregues pelos
Correios ou por transportadora. Cada chamado vai para exatamente uma de oito
filas de atendimento.
"""

from __future__ import annotations

import random

from ._common import integer, label_items, merge, order_id

SLUG = "ticket_classification_ptbr"
NAME = "Classificação de Chamados de Suporte (pt-BR)"
DESCRIPTION = (
    "1.200 chamados de suporte em português do Brasil para uma empresa que vende app por assinatura e aparelhos "
    "de casa inteligente, cada um direcionado a uma de 8 filas: cobrança, problema técnico, acesso à conta, "
    "entrega, troca/devolução, dúvida sobre produto, cancelamento ou sugestão."
)
LANGUAGE = "pt-BR"
TASK = "Qual fila de atendimento deve tratar este chamado do cliente?"

LABELS = [
    {
        "name": "cobranca",
        "description": (
            "Dinheiro já cobrado ou devido numa conta ou pedido existente: cobranças, faturas, boletos, Pix, notas "
            "fiscais e comprovantes, forma de pagamento e pagamento recusado, e-mail de cobrança, reajuste do plano "
            "atual e cobranças duplicadas, indevidas ou erradas — inclusive pedir o estorno de uma cobrança errada, "
            "mesmo que feita após cancelamento ou downgrade, ou de um frete cobrado errado. Reembolso de produto "
            "físico devolvido é troca_devolucao; preço antes de comprar é duvida_produto."
        ),
    },
    {
        "name": "problema_tecnico",
        "description": (
            "Algo no app, na API, numa integração ou num aparelho não funciona como deveria e o cliente quer que seja "
            "consertado: bugs, mensagens de erro, travamentos, falha de sincronização ou conexão, atualização de "
            "firmware que falha, lentidão. Problemas para entrar na conta (senha, verificação em duas etapas, "
            "bloqueio) são acesso_conta mesmo com erro na tela; querer devolver o aparelho com defeito é "
            "troca_devolucao; pedir algo que não existe é sugestao."
        ),
    },
    {
        "name": "acesso_conta",
        "description": (
            "Entrar na conta ou protegê-la: falha de login, redefinição de senha, verificação em duas etapas, conta "
            "bloqueada ou invadida, recuperação de acesso, troca do e-mail de login ou do nome de usuário, e dar ou "
            "tirar o acesso/admin de uma pessoa. Mudar o e-mail que recebe as faturas é cobranca; encerrar ou excluir "
            "a conta é cancelamento."
        ),
    },
    {
        "name": "entrega",
        "description": (
            "Situação ou entrega de um pedido que ainda não foi recebido (ou só em parte): separação, envio, "
            "rastreio, atraso, transportadora/Correios, mudança de endereço ou data de entrega, e pacote extraviado, "
            "não recebido, entregue no lugar errado ou devolvido ao remetente. Se o produto já chegou e veio "
            "danificado, errado ou não serviu, é troca_devolucao; contestar o valor do frete é cobranca."
        ),
    },
    {
        "name": "troca_devolucao",
        "description": (
            "Produto físico que o cliente já recebeu: devolver ou trocar (arrependimento, defeito, cor/modelo "
            "errado), item que chegou danificado, incompleto ou diferente do pedido, etiqueta/código de postagem e "
            "política de devolução, e o status do reembolso de um item devolvido. Estorno de cobrança errada sem "
            "produto devolvido é cobranca; pacote que nunca chegou é entrega."
        ),
    },
    {
        "name": "duvida_produto",
        "description": (
            "Dúvidas de pré-venda ou informativas sobre o que é oferecido: especificações e recursos dos aparelhos, "
            "compatibilidade, estoque e disponibilidade, garantia, planos, comparação de planos e preços de tabela, "
            "teste grátis e descontos. Perguntar se algo já existe é duvida_produto; pedir que seja criado é "
            "sugestao; dúvida sobre uma cobrança já feita é cobranca."
        ),
    },
    {
        "name": "cancelamento",
        "description": (
            "Encerrar ou reduzir uma assinatura ou conta: cancelar assinatura, plano ou pacote adicional, desativar "
            "a renovação automática, fazer downgrade para um plano mais barato ou gratuito, cancelar o teste antes "
            "de virar pago, encerrar ou excluir a conta. Se o pedido principal é o estorno de algo já cobrado, é "
            "cobranca; devolver aparelho é troca_devolucao."
        ),
    },
    {
        "name": "sugestao",
        "description": (
            "Sugestões ou pedidos de funcionalidades, integrações, compatibilidade ou melhorias de hardware que ainda "
            "não existem — inclusive melhorias nas telas de cobrança, login, rastreio ou assinatura. Função existente "
            "que quebrou é problema_tecnico; só perguntar se algo existe é duvida_produto."
        ),
    },
]

# ── Slots ───────────────────────────────────────────────────────────────

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
    "novembro", "dezembro",
]
DIAS_SEMANA = [
    ("na", "segunda", "passada"), ("na", "terça", "passada"), ("na", "quarta", "passada"),
    ("na", "quinta", "passada"), ("na", "sexta", "passada"), ("no", "sábado", "passado"),
    ("no", "domingo", "passado"),
]
# Todos os produtos são substantivos femininos, para "a/minha/da {produto}" concordar.
PRODUTOS = [
    "câmera Ipê Vista", "câmera Ipê Vista Externa", "lâmpada Ipê Luz", "fita de LED Ipê Luz",
    "tomada inteligente Ipê Plug", "caixa de som Ipê Som", "caixa de som Ipê Som Max", "fechadura Ipê Lock",
    "campainha Ipê Bell", "central Ipê Hub", "central Ipê Hub Mini", "luminária Ipê Desk", "balança Ipê Fit",
]
ACESSORIOS = [p for p in PRODUTOS if "central" not in p]
PRODUTOS_BATERIA = ["campainha Ipê Bell", "fechadura Ipê Lock", "câmera Ipê Vista Externa", "balança Ipê Fit"]
PARES_TROCA = [
    "a central Ipê Hub Mini pela central Ipê Hub", "a câmera Ipê Vista pela Ipê Vista Externa",
    "a caixa de som Ipê Som pela Ipê Som Max", "a lâmpada Ipê Luz pela fita de LED Ipê Luz",
    "a tomada Ipê Plug avulsa pelo kit com 4", "a luminária Ipê Desk pela fita de LED Ipê Luz",
]
VARIANTES = [
    "pela versão branca", "pela versão grafite", "pela versão verde-sálvia", "pela versão preta",
    "pelo kit com 2", "pelo kit com 4", "pelo kit inicial", "pelo modelo externo", "pelo modelo maior",
]
CORES = ["branca", "preta", "grafite", "verde-sálvia", "areia", "azul-marinho"]
PLANOS = ["Básico", "Plus", "Pro", "Equipe", "Empresarial"]
PLANOS_ALTOS = ["Pro", "Equipe", "Empresarial"]
PLANOS_BAIXOS = ["Básico", "Plus"]
APPS = ["o app", "o app de celular", "o painel web", "o app do computador", "o app da Ipê", "o app do tablet"]
RECURSOS = [
    "o editor de automações", "o relatório de energia", "o histórico de atividades", "a visão de calendário",
    "o criador de cenas", "o painel compartilhado", "a tela de convidados", "a central de alertas",
    "o mapa de dispositivos", "a aba de relatórios", "o resumo por cômodo", "o histórico de consumo",
    "a exportação em CSV", "a linha do tempo da câmera",
]
RECURSOS_PLANO = [
    "acesso de convidados", "suporte a várias casas", "acesso à API", "alertas personalizados",
    "relatório de energia", "automações ilimitadas", "histórico de vídeo de 30 dias", "perfis de administrador",
    "integração com o Tarefix", "logs de auditoria",
]
INTEGRACOES = ["Tarefix", "Contabilê", "Fluxo CRM", "Agendê", "Notaí", "Zentrik", "Brilho ERP", "Papo Pronto"]
NOVAS_INTEGRACOES = ["Caixinha PDV", "Folha Fácil", "Vendê CRM", "Mensagê", "Estoque Já", "Lojinha Online"]
PLATAFORMAS = [
    "a assistente de voz Corvo", "tablets Vela", "roteadores HomeLink", "rede Wi-Fi só de 5 GHz",
    "Wi-Fi em malha (mesh)", "celular antigo com Bluetooth 4.0", "computador com Linux", "TVs Kestrel",
    "a VPN da empresa", "a central Maestro", "tomada 220V",
]
PLATAFORMAS_PEDIDO = [
    "a assistente de voz Corvo", "tablets Vela", "TVs Kestrel", "a central Maestro", "computador com Linux",
]
NOVAS_FUNCIONALIDADES = [
    "modo escuro", "modo offline", "um widget pra tela inicial", "perfis de usuário personalizados",
    "um resumo semanal por e-mail", "sincronização com a agenda nos dois sentidos", "atalhos de teclado",
    "um modo férias", "relatórios em outros idiomas", "uma página pública de status", "metas de consumo por cômodo",
    "controles na tela de bloqueio", "temas personalizados pro painel", "um botão de desfazer nas automações",
    "um modo família", "um modo visita pra babá", "um relatório mensal de energia pra imprimir",
    "recado de voz nos alertas", "um modo de letra grande pra acessibilidade", "uma previsão do valor da conta de luz",
]
CAPACIDADES_NOVAS = [
    "reordenar os cômodos arrastando", "duplicar uma automação", "escolher um som de alerta pra cada dispositivo",
    "renomear vários dispositivos de uma vez", "agendar uma cena pra uma data específica",
    "colocar observações nos dispositivos", "exportar o histórico de atividades",
    "colocar o mesmo dispositivo em mais de um cômodo", "silenciar os alertas por um tempo",
    "compartilhar só uma câmera com o vizinho", "definir horário de silêncio pras notificações",
    "copiar uma cena pra outra casa", "colocar etiquetas personalizadas nos dispositivos",
    "fixar os dispositivos favoritos no topo", "criar automações pela temperatura do cômodo",
    "mandar os alertas pra um grupo de mensagens",
]
CAPACIDADES_Q = [
    "compartilhar um painel com alguém de fora da equipe", "agrupar dispositivos por andar",
    "disparar automações no nascer do sol", "exportar relatórios em PDF", "ver o histórico de bateria de um aparelho",
    "controlar as luzes pela tela de bloqueio", "dar acesso temporário pra um convidado",
    "controlar duas casas com o mesmo login",
]
MELHORIAS = [
    "deixasse filtrar por cômodo", "aceitasse períodos personalizados", "mostrasse dados por hora",
    "desse pra compartilhar com convidados", "lembrasse a última visualização", "tivesse uma busca",
    "mostrasse o total por semana",
]
MELHORIAS_HW = [
    "uma entrada USB-C", "bateria reserva", "um botão físico pra silenciar", "pilhas substituíveis",
    "uma luz de status mais fraca", "um cabo de energia mais comprido", "um modo noturno pro LED",
]
API_COISAS = [
    "atualizar vários dispositivos de uma vez", "puxar o histórico dos sensores",
    "ver o histórico de execução das automações", "gerenciar usuários", "consultar o status de firmware",
    "baixar os clipes de eventos da câmera", "mudar os dispositivos de cômodo", "ver o consumo de energia por aparelho",
]
PEDIDOS_PEQUENOS = [
    "lembrar o último filtro que usei", "mostrar a porcentagem de bateria na lista de dispositivos",
    "deixar renomear as cenas", "ordenar os dispositivos em ordem alfabética",
    "colocar uma busca no histórico de atividades", "deixar aumentar o tamanho da letra",
]
EVENTOS = [
    "bateria fraca", "dispositivo ficando offline", "fim de atualização de firmware",
    "usuário novo entrando no espaço de trabalho", "detecção de movimento",
]
FORMATOS = ["XLSX", "PDF", "JSON", "XML", "ODS", "TXT"]
SSO = ["chave de acesso (passkey)", "o login único (SSO) da empresa", "link mágico por e-mail", "Keyport SSO"]
ERROS_HTTP = [
    "erro 500", "erro 502", "erro 503", "timeout 504", "erro 500 intermitente",
    "erro 429 mesmo com pouco volume", "resposta vazia", "JSON malformado",
]
NOMES = [
    "Ana", "João", "Mariana", "Pedro", "Larissa", "Rafael", "Camila", "Lucas", "Beatriz", "Gustavo", "Fernanda",
    "Thiago", "Juliana", "Bruno", "Letícia", "Felipe", "Aline", "Rodrigo", "Patrícia", "Diego", "Vanessa", "Marcos",
]
SOBRENOMES = [
    "Silva", "Souza", "Oliveira", "Santos", "Lima", "Pereira", "Costa", "Almeida", "Ferreira", "Rodrigues",
    "Carvalho", "Gomes", "Ribeiro", "Martins",
]
CIDADES_LOGIN = ["Lisboa", "Manaus", "Buenos Aires", "Santiago", "Miami", "Luanda", "Porto", "Assunção", "Madri"]
CIDADES = [
    "Campinas", "Curitiba", "Recife", "Belo Horizonte", "Porto Alegre", "Goiânia", "Salvador", "Florianópolis",
    "Fortaleza", "Niterói", "Londrina", "Natal",
]
DOMINIOS = [
    "exemplo.com.br", "correio.exemplo", "padariabomgosto.com.br", "construtoraalfa.com.br", "studiorosa.com.br",
    "contabilprime.com.br",
]
RUAS = [
    "Rua das Acácias", "Rua dos Ipês", "Av. Sete de Setembro", "Rua XV de Novembro", "Rua das Palmeiras",
    "Av. Tiradentes", "Rua Barão do Rio Branco", "Rua das Flores", "Av. Santos Dumont", "Travessa São José",
]
BAIRROS = ["Centro", "Jardim América", "Vila Nova", "Boa Vista", "Santa Cecília", "Jardim Botânico", "Bela Vista"]
DESCONTOS = ["10", "15", "20", "25", "30", "40"]

CONTA_REFS = ["minha conta", "a conta da empresa", "a conta de admin", "minha conta Ipê", "a conta da minha casa"]
CONTA_REFS_CANCEL = ["minha conta", "a conta da empresa", "minha conta Ipê", "a conta da minha casa", "a conta da loja"]
PERDI_CELULAR = [
    "Perdi o celular", "Meu celular foi roubado", "Troquei de celular", "Meu celular quebrou", "Formatei o celular",
    "Meu celular caiu na piscina",
]
NA_HORA = ["na hora", "no mesmo minuto", "assim que chega", "segundos depois de receber"]
NA_CONTA = ["na minha conta", "na conta da empresa", "na conta de admin", "pra toda a equipe"]
MOTIVOS_SEGURANCA = [
    "", "O pessoal da segurança tá exigindo.", "Recebi um e-mail suspeito e fiquei com medo.", "A auditoria pediu.",
    "Hackearam a conta de um amigo semana passada.",
]
APARELHOS_ANTIGOS = ["celular antigo", "celular do trabalho", "tablet antigo", "celular pessoal"]
DESTINOS_APARELHO = ["vender ele", "formatar", "dar pro meu filho", "mandar pro conserto", "devolver pra empresa"]
ESPERAS = ["24 horas", "12 horas", "uma hora", "até amanhã"]
EXPORTAR_O_QUE = [
    "o histórico de atividades", "os dados de energia", "as leituras dos sensores", "a lista de dispositivos",
    "o histórico das automações", "os eventos da câmera",
]
PRODUTOS_EXTERNOS = ["câmera Ipê Vista Externa", "campainha Ipê Bell", "fechadura Ipê Lock"]
CLIMAS = ["chuva forte", "sol direto o dia todo", "maresia", "geada", "poeira de obra"]
USOS = ["", " com uso normal", " no frio", " se eu usar todo dia", " no modo economia"]
EXCL_TAILS = ["", " pelo app", " e tiro todos os aparelhos", " junto com as gravações da câmera", " pra vcs não ficarem com meus dados"]
MOTIVOS_CURTOS = [
    "Se precisar, eu volto.", "Vou me mudar pro exterior.", "A grana tá curta.", "Vendemos a casa.",
    "Mudei de emprego.", "Não uso o suficiente.",
]
ADICIONAIS = ["armazenamento extra", "histórico de vídeo", "usuários extras", "suporte premium", "alertas por SMS", "relatórios avançados"]
DADOS_TAILS = ["", ", inclusive as gravações da câmera", ", inclusive o histórico dos aparelhos", " e me confirmar quando terminar", " o quanto antes"]


def brl(low: int = 19, high: int = 2500):
    """Valores no formato brasileiro: 'R$ 89', 'R$ 1.234,56'."""

    def _gen(rng: random.Random) -> str:
        return _brl_fmt(rng.uniform(low, high), rng.random() < 0.4)

    return _gen


def _brl_fmt(value: float, whole: bool) -> str:
    if whole:
        return "R$ " + f"{int(value):,}".replace(",", ".")
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def aumento(rng: random.Random) -> str:
    """'de R$ 49 para R$ 79' — reajuste plausível (+15% a +120%)."""
    base = rng.uniform(19, 900)
    whole = rng.random() < 0.4
    return f"de {_brl_fmt(base, whole)} para {_brl_fmt(base * rng.uniform(1.15, 2.2), whole)}"


def quando(rng: random.Random) -> str:
    """Advérbio de tempo autônomo: 'ontem', 'dia 12', 'na sexta passada', 'há 5 dias', 'em 12/03'."""
    style = rng.randint(0, 5)
    if style == 0:
        return f"dia {rng.randint(1, 28)}"
    if style == 1:
        prep, dia, adj = rng.choice(DIAS_SEMANA)
        return f"{prep} {dia} {adj}"
    if style == 2:
        return f"há {rng.randint(2, 14)} dias"
    if style == 3:
        return f"em {rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}"
    if style == 4:
        return f"no dia {rng.randint(1, 28)} de {rng.choice(MESES)}"
    return rng.choice(["ontem", "anteontem", "semana passada", "hoje cedo", "no começo da semana"])


def desde_dia(rng: random.Random) -> str:
    """Data que cabe depois de 'desde'/'antes de': 'dia 12', 'segunda', '12/03', '3 de maio'."""
    style = rng.randint(0, 3)
    if style == 0:
        return f"dia {rng.randint(1, 28)}"
    if style == 1:
        return rng.choice(DIAS_SEMANA)[1]
    if style == 2:
        return f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}"
    return f"{rng.randint(1, 28)} de {rng.choice(MESES)}"


def desde(rng: random.Random) -> str:
    return rng.choice([
        "desde ontem", "desde hoje cedo", "faz dois dias", "a semana toda", "desde a última atualização",
        f"desde {desde_dia(rng)}", f"desde {desde_dia(rng)}", "faz umas horas", "desde que atualizamos o app",
        "faz uma semana",
    ])


def erro(rng: random.Random) -> str:
    style = rng.randint(0, 4)
    if style == 0:
        return f"erro {rng.choice(['500', '502', '503', '504', '422', '408'])}"
    if style == 1:
        return f"erro E{rng.randint(100, 999)}"
    if style == 2:
        return f"código de erro ERR-{rng.randint(1000, 9999)}"
    if style == 3:
        return f"erro 0x{rng.randint(4096, 65535):X}"
    return rng.choice([
        "a mensagem 'Algo deu errado'", "a mensagem 'Erro inesperado no servidor'",
        "a mensagem 'Tempo esgotado'", "o aviso 'Falha na sincronização'",
    ])


NOMES_F = ["Ana", "Mariana", "Larissa", "Camila", "Beatriz", "Fernanda", "Juliana", "Letícia", "Aline", "Patrícia", "Vanessa"]
NOMES_M = ["João", "Pedro", "Rafael", "Lucas", "Gustavo", "Thiago", "Bruno", "Felipe", "Rodrigo", "Diego", "Marcos"]
PARES_COMPARAR = [
    "a central Ipê Hub Mini e a central Ipê Hub", "a câmera Ipê Vista e a Ipê Vista Externa",
    "a caixa de som Ipê Som e a Ipê Som Max", "a lâmpada Ipê Luz e a fita de LED Ipê Luz",
    "a campainha Ipê Bell e a câmera Ipê Vista Externa", "a luminária Ipê Desk e a lâmpada Ipê Luz",
]


def erro_login(rng: random.Random) -> str:
    style = rng.randint(0, 2)
    if style == 0:
        return f"erro E{rng.randint(400, 499)}"
    if style == 1:
        return f"código de erro AUTH-{rng.randint(100, 999)}"
    return rng.choice(["a mensagem 'Código inválido'", "a mensagem 'Falha na verificação'", "a mensagem 'Código expirado'"])


_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")


def _ascii(text: str) -> str:
    return text.lower().translate(_ACENTOS)


def nome(rng: random.Random) -> str:
    return f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)}"


def email(rng: random.Random) -> str:
    first, last = _ascii(rng.choice(NOMES)), _ascii(rng.choice(SOBRENOMES))
    local = rng.choice([f"{first}.{last}", f"{first}{last[0]}", f"{first[0]}{last}", f"{first}.{last}{rng.randint(1, 99)}"])
    return f"{local}@{rng.choice(DOMINIOS)}"


def usuario(rng: random.Random) -> str:
    first, last = _ascii(rng.choice(NOMES)), _ascii(rng.choice(SOBRENOMES))
    return rng.choice([f"{first}{rng.randint(1, 999)}", f"{first}_{last}", f"{first[0]}{last}{rng.randint(1, 99)}"])


def endereco(rng: random.Random) -> str:
    base = f"{rng.choice(RUAS)}, {rng.randint(10, 3999)}"
    if rng.random() < 0.35:
        base += f", apto {rng.randint(11, 304)}"
    return f"{base} - {rng.choice(BAIRROS)}, {rng.choice(CIDADES)}"


def fatura(rng: random.Random) -> str:
    return f"FAT-{rng.choice(['2025', '2026'])}-{rng.randint(1000, 99999)}"


def nota_fiscal(rng: random.Random) -> str:
    return f"{rng.randint(1000, 999999)}"


def protocolo(rng: random.Random) -> str:
    return f"DEV-{rng.randint(10000, 99999)}"


def final_cartao(rng: random.Random) -> str:
    return f"{rng.randint(0, 9999):04d}"


def item_errado(rng: random.Random) -> str:
    a, b = rng.sample(PRODUTOS, 2)
    return f"uma {a} no lugar da {b} que eu pedi"


def ja_tenho(rng: random.Random) -> str:
    a, b = rng.sample(ACESSORIOS, 2)
    return f"Já tenho uma {a}; antes de comprar outro aparelho, queria saber se a {b} funciona junto com ela."


def cap(pool):
    return lambda rng: (lambda s: s[0].upper() + s[1:])(rng.choice(pool))


SLOTS = {
    "valor": brl(),
    "valor_baixo": brl(19, 400),
    "valor_alto": brl(450, 3000),
    "pedido": lambda rng: order_id(rng, "PED"),
    "quando": quando,
    "desde": desde,
    "desde_dia": desde_dia,
    "mes": MESES,
    "produto": PRODUTOS,
    "acessorio": ACESSORIOS,
    "produto_bateria": PRODUTOS_BATERIA,
    "par_troca": PARES_TROCA,
    "item_errado": item_errado,
    "ja_tenho": ja_tenho,
    "variante": VARIANTES,
    "cor": CORES,
    "plano": PLANOS,
    "plano_alto": PLANOS_ALTOS,
    "plano_baixo": PLANOS_BAIXOS,
    "app": APPS,
    "App": cap(APPS),
    "recurso": RECURSOS,
    "Recurso": cap(RECURSOS),
    "recurso_plano": RECURSOS_PLANO,
    "Recurso_plano": cap(RECURSOS_PLANO),
    "integracao": INTEGRACOES,
    "nova_integracao": NOVAS_INTEGRACOES,
    "plataforma": PLATAFORMAS,
    "plataforma_pedido": PLATAFORMAS_PEDIDO,
    "nova_funcionalidade": NOVAS_FUNCIONALIDADES,
    "capacidade_nova": CAPACIDADES_NOVAS,
    "capacidade_q": CAPACIDADES_Q,
    "melhoria": MELHORIAS,
    "melhoria_hw": MELHORIAS_HW,
    "api_coisa": API_COISAS,
    "pedido_pequeno": PEDIDOS_PEQUENOS,
    "evento": EVENTOS,
    "formato": FORMATOS,
    "sso": SSO,
    "erros_http": ERROS_HTTP,
    "Erros_http": cap(ERROS_HTTP),
    "erro": erro,
    "segs": integer(8, 45),
    "pct": integer(12, 97),
    "desconto": DESCONTOS,
    "n": integer(3, 21),
    "n_unid": integer(5, 60),
    "n2": integer(2, 6),
    "assentos": integer(20, 90),
    "assentos_menor": integer(3, 15),
    "fatura": fatura,
    "nf": nota_fiscal,
    "protocolo": protocolo,
    "final": final_cartao,
    "email": email,
    "email2": email,
    "usuario": usuario,
    "nome": nome,
    "nome2": nome,
    "cidade_login": CIDADES_LOGIN,
    "cidade": CIDADES,
    "dominio": DOMINIOS,
    "endereco": endereco,
    "ano": ["2024", "2025"],
    "conta_ref": CONTA_REFS,
    "Conta_ref": cap(CONTA_REFS),
    "conta_ref2": CONTA_REFS_CANCEL,
    "Perdi_celular": PERDI_CELULAR,
    "na_hora": NA_HORA,
    "na_conta": NA_CONTA,
    "na_conta_login": ["na minha conta", "na conta da empresa", "na conta de admin", "na minha conta Ipê", "na conta da minha casa"],
    "motivo_seguranca": MOTIVOS_SEGURANCA,
    "aparelho_antigo": APARELHOS_ANTIGOS,
    "destino_aparelho": DESTINOS_APARELHO,
    "espera": ESPERAS,
    "exportar_o_que": EXPORTAR_O_QUE,
    "produto_externo": PRODUTOS_EXTERNOS,
    "clima": CLIMAS,
    "uso": USOS,
    "excl_tail": EXCL_TAILS,
    "motivo_curto": MOTIVOS_CURTOS,
    "adicional": ADICIONAIS,
    "dados_tail": DADOS_TAILS,
    "cancel_tail": ["", " hoje mesmo", " com efeito imediato", " no fim do mês", " antes da próxima cobrança", " — o e-mail da conta é {email}"],
    "fim_quando": ["no fim do mês", "em {mes}", "semana que vem", "agora no fim do trimestre"],
    "no_recurso": [("no " + r[2:]) if r.startswith("o ") else ("na " + r[2:]) for r in RECURSOS],
    "nome_f": lambda rng: f"{rng.choice(NOMES_F)} {rng.choice(SOBRENOMES)}",
    "nome_m": lambda rng: f"{rng.choice(NOMES_M)} {rng.choice(SOBRENOMES)}",
    "erro_login": erro_login,
    "aumento": aumento,
    "Quantos_disp": [
        "Quantos dispositivos", "Quantas câmeras", "Quantos sensores", "Quantas tomadas inteligentes",
        "Quantas lâmpadas", "Quantas fechaduras",
    ],
    "par_comparar": PARES_COMPARAR,
    "tipo_casa": ["apartamento pequeno", "casa de dois andares", "home office", "imóvel de aluguel", "família com criança"],
    "de_quem": ["da nossa contabilidade", "do nosso contador", "do financeiro", "da nossa contadora"],
}

PREFIXES = [
    "Oi,", "Olá,", "Bom dia,", "Boa tarde,", "Boa noite,", "Oi pessoal,", "Olá, equipe Ipê.", "Oi, tudo bem?",
    "Olá, suporte.",
]
SUFFIXES = [
    "Obrigado.", "Obrigada!", "Aguardo retorno.", "Valeu!", "Desde já agradeço.", "Fico no aguardo.", "Att.",
    "Obrigado pela ajuda.", "Aguardo resposta, por favor.",
]

# ── Templates ───────────────────────────────────────────────────────────

TEMPLATES = {
    "cobranca": [
        "Fui cobrado duas vezes pela assinatura {plano}, {valor} cada, {quando}. Quero o estorno da cobrança duplicada.",
        "Por que minha fatura de {mes} veio {valor_alto} se o plano custa {valor_baixo}?",
        "Preciso da nota fiscal da mensalidade de {mes} do plano {plano}, não chegou no meu e-mail.",
        "O boleto da fatura {fatura} venceu {quando} e não consigo gerar a segunda via. Podem me mandar?",
        "Paguei via Pix {quando} e o sistema ainda mostra a fatura {fatura} em aberto.",
        "Apareceu uma cobrança de {valor} da Ipê no meu cartão {quando} que eu não reconheço. Do que se trata?",
        "Quero trocar o cartão de crédito cadastrado no plano {plano}, o atual vence esse mês.",
        "Vcs cobraram {assentos} usuários mas a gente só tem {assentos_menor} ativos. Corrige a fatura {fatura} pfv.",
        "A nota fiscal {nf} saiu com o CNPJ errado, precisa ser emitida no nome da nossa empresa.",
        "Quero mudar a forma de pagamento da assinatura {plano} de cartão pra boleto. Como faço?",
        "O valor da mensalidade subiu {aumento} sem nenhum aviso. Isso tá certo?",
        "Meu cartão final {final} foi recusado na renovação do plano {plano}, mas o banco diz que tá tudo certo.",
        "Fiz upgrade pro {plano_alto} no meio do mês e cobraram o mês cheio, {valor}. Não deveria ser proporcional?",
        "Tinha {desconto}% de desconto no plano anual e cobraram o valor cheio de {valor}.",
        "Preciso do comprovante do pagamento de {valor} que fiz {quando}, é pra contabilidade.",
        "Cobrança indevida de {valor} no cartão final {final} por um pedido que eu nunca fiz. Quero meu dinheiro de volta.",
        "Podem mandar as faturas pro e-mail do financeiro, {email}? Hoje chegam só pra mim.",
        "O débito automático que caiu {quando} foi de {valor_alto}, mas a fatura {fatura} é de {valor_baixo}. Qual tá certo?",
        "cobrança duplicada de novo!!! {valor} duas vezes {quando}",
        "Quero entender a cobrança de {valor} de 'excedente de uso' na fatura de {mes}.",
        "O boleto que vcs mandaram tá com valor errado, era pra ser {valor_baixo} e veio {valor_alto}.",
        "Não recebi a nota fiscal do pedido {pedido}, preciso dela pra declarar.",
        "Paguei o boleto da fatura {fatura} {quando} e continuam me mandando aviso de cobrança. Já tá pago!",
        "Cobraram {valor} por um pacote adicional que a gente nunca ativou. Tirem e devolvam o valor, por favor.",
        "Dá pra pagar as faturas do plano {plano} por Pix em vez de cartão?",
        "fatura {fatura} errada, nosso plano é {plano_baixo} e não {plano_alto}",
    ],
    "problema_tecnico": [
        "{App} fecha sozinho toda vez que abro {recurso}.",
        "{Recurso} não funciona {desde}, fica só carregando.",
        "A integração com o {integracao} dá {erro} sempre que tentamos sincronizar.",
        "A API tá retornando {erros_http} no endpoint /dispositivos {desde}.",
        "Minha {produto} fica desconectando do Wi-Fi a cada poucas horas e tenho que tirar da tomada pra voltar.",
        "{App} tá muito lento, as páginas demoram uns {segs} segundos pra carregar.",
        "Dá {erro} quando tento salvar uma automação. Já testei em dois navegadores.",
        "A {produto} aparece offline no app, mas a luz dela tá verde.",
        "Depois da última atualização, {recurso} mostra dados do dia errado.",
        "Os webhooks não chegam no nosso servidor {desde} e o log de entregas tá vazio.",
        "A atualização de firmware da {produto} trava em {pct}% e o aparelho reinicia.",
        "Exportar {exportar_o_que} em CSV gera um arquivo vazio, qualquer período que eu escolha.",
        "As notificações do app não chegam no meu celular {desde}.",
        "{App} trava na tela de pareamento quando tento adicionar a {produto} nova.",
        "A {produto} não pareia por Bluetooth, o app só diz 'dispositivo não encontrado'.",
        "Os dados da {produto} não estão sincronizando, a última leitura é de {desde_dia}.",
        "Os gráficos do painel estão em branco pra todo mundo da equipe {desde}.",
        "{Erros_http} em todas as requisições da API {desde}, nossa integração tá fora do ar. Urgente!",
        "As automações estão disparando duas vezes {desde}, toda ação agendada roda em dobro.",
        "O upload da planta da casa falha com {erro}, não importa o tamanho do arquivo.",
        "O som da caixa de som Ipê Som fica cortando a cada {segs} segundos quando toco música pelo app.",
        "A busca do app não acha nenhum dispositivo, nem os que aparecem na lista.",
        "app bugado de novo, {recurso} não abre",
        "A câmera Ipê Vista grava, mas {desde} os vídeos não aparecem na linha do tempo do app.",
        "{Recurso} dá {erro} assim que eu abro.",
        "O conector do {integracao} se desconecta sozinho toda noite e a gente tem que reconectar de manhã.",
    ],
    "acesso_conta": [
        "Esqueci minha senha e o link de redefinição não chega no {email}.",
        "{Conta_ref} foi bloqueada depois de várias tentativas de login. Como desbloqueio?",
        "{Perdi_celular} e não recebo mais o código da verificação em duas etapas. Me ajudem a entrar {na_conta_login}.",
        "Preciso trocar o e-mail da minha conta de {email} para {email2}.",
        "O link pra redefinir a senha diz que expirou, mesmo clicando {na_hora}. Já pedi {n2} links novos.",
        "Não consigo fazer login, aparece 'senha incorreta' mas tenho certeza que tá certa. Meu usuário é {usuario}.",
        "O SMS com o código de acesso não chega no meu número final {final} quando tento entrar.",
        "Como ativo a verificação em duas etapas {na_conta}? {motivo_seguranca}",
        "{nome}, que era admin da nossa conta, saiu da empresa e precisamos passar o acesso de admin pra {nome2}.",
        "Criei a conta com {email} mas não tenho mais acesso a esse e-mail. Como entro na minha conta?",
        "Recebi um alerta de login em {cidade_login} que não fui eu. Acho que invadiram minha conta, me ajudem.",
        "Podem resetar minha senha? Meu usuário é {usuario}.",
        "Resetei o app autenticador {quando} e agora nenhum código funciona pra entrar na conta.",
        "Quero mudar meu nome de usuário, o atual ({usuario}) tá com erro de digitação.",
        "Tô sem acesso à conta desde {desde_dia} e ninguém respondeu meu último e-mail.",
        "Mudamos o domínio da empresa para {dominio}. Como atualizo o e-mail de login da minha conta?",
        "Configurei a verificação em duas etapas no {aparelho_antigo}. Como passo pro novo antes de {destino_aparelho}?",
        "Um funcionário saiu da empresa, por favor tirem o acesso de {email} à nossa conta.",
        "não consigo logar com o {email}, socorro, preciso entrar hoje",
        "Aparece que {conta_ref} tá bloqueada por segurança. O que preciso fazer pra confirmar minha identidade?",
        "Não lembro com qual e-mail me cadastrei. Dá pra achar minha conta pelo nome {nome}?",
        "Errei a senha algumas vezes e agora diz pra esperar {espera}. Tem como liberar antes?",
        "Preciso recuperar o acesso da conta da minha mãe, {nome_f}. Ela esqueceu a senha e não lembra qual e-mail usou no cadastro.",
        "Troquei a senha {quando} e agora a nova não é aceita no login.",
        "Adicionem {nome2} também como admin da conta, pra gente não ficar sem acesso quando eu estiver fora.",
    ],
    "entrega": [
        "Cadê meu pedido {pedido}? Era pra ter chegado {quando}.",
        "O rastreio do pedido {pedido} não atualiza há {n} dias.",
        "Coloquei o endereço errado no pedido {pedido}. Dá pra mudar para {endereco}?",
        "O rastreio diz que o pedido {pedido} foi entregue, mas não recebi nada, nem na portaria.",
        "Quando o pedido {pedido} vai ser enviado? Comprei {quando}.",
        "Podem me passar o código de rastreio da minha {produto}?",
        "O entregador veio quando eu não tava em casa. Como reagendo a entrega do pedido {pedido}?",
        "Pedido {pedido} parado 'em trânsito' no mesmo centro de distribuição desde {desde_dia}.",
        "Paguei frete expresso e a {produto} ainda não chegou depois de {n} dias.",
        "Meu pedido {pedido} já foi despachado? Não recebi e-mail de envio.",
        "Dá pra entregar o pedido {pedido} no meu trabalho, na {endereco}, em vez de em casa?",
        "O rastreio dos Correios da minha {produto} só mostra 'objeto postado' faz {n} dias.",
        "Tem previsão nova de entrega pra {produto} que comprei {quando}? Tá aparecendo como atrasada.",
        "Meu pedido {pedido} veio dividido em dois volumes e só um chegou até agora.",
        "A transportadora deixou o pedido {pedido} no endereço errado, a foto da entrega nem é da minha casa.",
        "cadê minha encomenda?? pedido {pedido}",
        "O pedido {pedido} tá 'em separação' há mais de uma semana. Aconteceu alguma coisa?",
        "Qual transportadora vai entregar meu pedido {pedido}? No site não diz.",
        "A previsão de entrega da minha {produto} fica mudando. Primeiro era {desde_dia}, agora nem tem data.",
        "Já faz {n} dias e o pedido {pedido} não chegou. Que absurdo.",
        "Recebi um aviso de que o pedido {pedido} tá aguardando retirada numa agência dos Correios, mas não diz qual. Onde eu busco?",
        "Moro em {cidade} e o rastreio do pedido {pedido} mostra que ele foi pra outra cidade. O que houve?",
        "Vou viajar semana que vem, dá pra segurar a entrega do pedido {pedido} até eu voltar?",
        "Me mudei faz pouco tempo. Podem confirmar se o pedido {pedido} vai pra {endereco}?",
        "Minha {produto} comprada {quando} continua 'aguardando envio'. Quando sai do estoque?",
    ],
    "troca_devolucao": [
        "Quero devolver a {produto} que comprei, não era o que eu esperava.",
        "A {produto} chegou com a carcaça trincada. Quero uma nova.",
        "Vcs me mandaram {item_errado}. Pedido {pedido}.",
        "Como consigo a etiqueta de devolução do pedido {pedido}?",
        "Devolvi a {produto} faz {n} dias. Quando cai o reembolso?",
        "Posso trocar minha {produto} {variante}?",
        "A caixa veio amassada e a {produto} tá com um amassado. Quero devolver.",
        "Ainda dá tempo de devolver a {produto}? Comprei faz {n} dias e nem abri a caixa.",
        "A {produto} veio sem o carregador na caixa. Vcs mandam a peça ou eu devolvo tudo?",
        "Vcs receberam minha devolução faz {n} dias, mas o reembolso de {valor} ainda não saiu.",
        "Pedi a {produto} na cor {cor} e veio de outra cor. Quero trocar.",
        "A devolução do pedido {pedido} aparece como recebida. Em quanto tempo o estorno cai no cartão?",
        "Quero devolver a {produto} e receber o dinheiro de volta, não serviu pra mim.",
        "A {produto} já veio com defeito, nem liga. Quero trocar por outra.",
        "Recebi duas unidades da {produto} mas só pedi uma. Como devolvo a que veio a mais?",
        "Preciso da embalagem original pra devolver a {produto}?",
        "Dá pra devolver só uma das {n2} unidades do pedido {pedido}?",
        "Quero trocar {par_troca} e pagar a diferença.",
        "Ganhei uma {produto} de presente, mas já tenho uma. Posso trocar por vale-compras?",
        "O código de postagem que vcs mandaram pra devolução do pedido {pedido} não funciona na agência. Como devolvo?",
        "A tela da {produto} veio arranhada. Quero trocar.",
        "Reembolso da devolução {protocolo} ainda pendente depois de {n} dias.",
        "A embalagem veio aberta e a {produto} parecia usada. Quero uma nova ou meu dinheiro de volta.",
        "Me arrependi da compra da {produto}, recebi faz {n2} dias. Ainda tô dentro dos 7 dias pra desistir?",
        "Qual a política de devolução? A {produto} chegou {quando} e quero mandar de volta.",
    ],
    "duvida_produto": [
        "A {produto} funciona com {plataforma}?",
        "Qual a diferença entre o plano {plano_baixo} e o {plano_alto}?",
        "A {produto} voltou pro estoque? Tá aparecendo esgotada faz tempo.",
        "O plano {plano} inclui {recurso_plano}?",
        "{Quantos_disp} dá pra conectar numa central Ipê Hub? A ideia é ter uns {n_unid}.",
        "A {produto_externo} aguenta {clima} ou precisa de alguma proteção?",
        "Queremos comprar {n_unid} unidades da {produto} pro escritório. Tem desconto por quantidade?",
        "Dá pra testar o plano {plano_alto} antes de assinar? Tem período grátis?",
        "Quanto dura a bateria da {produto_bateria}{uso}?",
        "O plano {plano} permite quantos usuários?",
        "A {produto} continua funcionando se o Wi-Fi cair?",
        "A {produto} é bivolt?",
        "Qual a diferença entre {par_comparar}? Qual vcs indicam pra {tipo_casa}?",
        "A {acessorio} funciona com a central Ipê Hub Mini antiga ou preciso da nova?",
        "O plano {plano_alto} tem atendimento prioritário?",
        "Quando a {produto} na cor {cor} volta a ficar disponível?",
        "Dá pra instalar a {produto} na parede? Vem com suporte?",
        "Todos os planos incluem {recurso_plano} ou só os pagos?",
        "A API de vcs tem limite de requisições no plano {plano}? Estamos comparando fornecedores.",
        "O que vem na caixa do kit inicial da {produto}?",
        "Tem desconto pra estudante ou ONG no plano {plano}?",
        "Dá pra usar o app da Ipê no plano {plano} sem comprar nenhum aparelho?",
        "Antes de comprar: qual a garantia da {produto}?",
        "A integração com o {integracao} tá disponível no plano {plano_baixo} ou só nos superiores?",
        "Quanto custa o plano {plano_alto} por usuário pra uma equipe de {assentos} pessoas?",
        "A {acessorio} precisa da central Ipê Hub ou conecta direto no Wi-Fi?",
    ],
    "cancelamento": [
        "Quero cancelar minha assinatura {plano}{cancel_tail}.",
        "Quero encerrar {conta_ref2} e apagar todos os dados{dados_tail}.",
        "Como desativo a renovação automática? Não quero renovar em {mes}.",
        "Façam o downgrade do {plano_alto} pro {plano_baixo} no fim do ciclo atual, por favor.",
        "Vamos migrar pra outra ferramenta, cancelem a assinatura da equipe a partir de {desde_dia}.",
        "cancela minha assinatura {plano} pfv",
        "Não quero que minha assinatura {plano} renove no mês que vem.",
        "Dá pra cancelar o plano anual {plano} no fim do período, em {mes}, em vez de renovar?",
        "Por favor, encerrem a conta cadastrada no e-mail {email}.",
        "Vou cancelar. O plano {plano} tá caro demais pro tanto que eu uso.",
        "Como excluo minha conta da Ipê de vez{excl_tail}?",
        "Nossa empresa vai fechar {fim_quando}; cancelem o plano {plano} e encerrem o espaço de trabalho.",
        "Quero voltar pro plano gratuito, não preciso mais de {recurso_plano}.",
        "Parem de renovar meu plano {plano}. {motivo_curto}",
        "Cliquei em cancelar o plano {plano} {quando} mas não veio confirmação nenhuma. Foi cancelado mesmo?",
        "Comecei o teste do plano {plano_alto} {quando} e não quero continuar no pago. Como cancelo antes de virar cobrança?",
        "Cancelem o pacote de {adicional} da nossa conta, não usamos mais.",
        "Queremos rescindir o contrato do plano {plano} no fim da vigência, em {mes}.",
        "Quero cancelar o plano {plano}, quase não uso mais {app}.",
        "Estamos unificando as contas — encerrem a conta duplicada no e-mail {email}.",
        "Qual o prazo de aviso pra cancelar o contrato do plano {plano_alto} antes da renovação de {mes}?",
        "Tira minha assinatura {plano}, vou ficar só com a versão grátis.",
        "Quero cancelar a assinatura {plano} do meu pai, {nome_m}, ele não usa mais.",
        "Daqui pra frente só precisamos do {plano_baixo}. Baixem nosso plano do {plano_alto} antes da renovação de {mes}.",
    ],
    "sugestao": [
        "Seria ótimo se o app tivesse {nova_funcionalidade}.",
        "Por favor, adicionem {nova_funcionalidade}. Nossa equipe usaria todo dia.",
        "Sugestão: {nova_funcionalidade}.",
        "Vcs pensam em lançar {nova_funcionalidade}? Ia ajudar muito.",
        "Sugestão: deixar a gente {capacidade_nova} direto pelo painel.",
        "Pensem em fazer a {produto} funcionar com {plataforma_pedido}; hoje não funciona e eu compraria mais duas.",
        "{Recurso} seria bem mais útil se {melhoria}.",
        "Podiam colocar {nova_funcionalidade} no app de celular também.",
        "Ideia pro roadmap: {nova_funcionalidade}.",
        "A gente pagaria a mais por {nova_funcionalidade}. Fica a dica.",
        "Dá pra incluir uma opção de {capacidade_nova}? Hoje a gente faz tudo na mão.",
        "Adoro a {produto}, mas a próxima versão precisa de {melhoria_hw}.",
        "Queria muito poder {capacidade_nova}.",
        "Meu único pedido: {nova_funcionalidade}. Fora isso o app é perfeito.",
        "Alguém já pediu {nova_funcionalidade}? Deixo meu voto.",
        "Seria ótimo ter um endpoint na API pra {api_coisa}.",
        "O painel devia deixar a gente {capacidade_nova}.",
        "Façam uma integração com o {nova_integracao}, a gente usa pra tudo aqui.",
        "Sugestão pra {produto}: {melhoria_hw} ia deixar ela muito melhor.",
        "Pedido pequeno: {pedido_pequeno}.",
        "Bem que {app} podia ter {nova_funcionalidade}, né?",
        "Fica a sugestão de {nova_funcionalidade}, os concorrentes já têm.",
        "Os admins aqui vivem pedindo um jeito de {capacidade_nova}. Dá pra vcs criarem isso?",
    ],
}

HARD = {
    "cobranca": [
        "O app tá funcionando normal, o problema é uma cobrança de {valor} {quando} por uma renovação que eu não autorizei. Quero esse valor de volta.",
        "Cancelamos o plano {plano} lá em {mes} e mesmo assim vcs cobraram {valor} na última renovação. Quero o estorno dessa cobrança.",
        "Fiz o downgrade pro {plano_baixo} no mês passado, mas a cobrança veio no valor do {plano_alto}, {valor}. Só preciso que corrijam a cobrança.",
        "O pedido {pedido} chegou certinho, sem problema com a entrega — mas me cobraram {valor} de frete expresso e eu escolhi o frete grátis.",
        "Não quero devolver a {produto}, gostei muito — mas passaram duas cobranças de {valor} no cartão pelo pedido {pedido}. Quero o estorno da segunda.",
        "Consigo entrar na conta normal, só não acho onde atualizar o cartão pra próxima cobrança do plano {plano}.",
        "Não é bug não: a fatura {fatura} mostra {assentos} usuários e a gente paga por {assentos_menor}.",
        "Não quero mudar de plano, só preciso que alguém explique essa cobrança de {valor} de 'excedente' na fatura de {mes}.",
        "Não vou cancelar nada, mas a renovação subiu {aumento} sem aviso e quero que corrijam.",
    ],
    "problema_tecnico": [
        "Consigo entrar na conta sem problema, mas logo depois do login {recurso} congela e a aba trava.",
        "Não é sugestão não — {recurso} funcionava semana passada e agora dá {erro}.",
        "A {produto} chegou perfeita e não quero devolver; ela só não conecta no app ({erro}).",
        "Nossa assinatura tá paga e ativa, mas a API tá retornando {erros_http} {desde}.",
        "Não quero reembolso, quero que arrumem a sincronização com o {integracao}. Tá falhando {desde}.",
        "A entrega foi rápida, mas a atualização de firmware da {produto} trava em {pct}% e não consigo usar.",
        "O login com verificação em duas etapas funciona, mas depois disso cada página do app leva {segs} segundos pra abrir.",
        "Não tô pedindo nada novo — o botão de exportar que já existe {no_recurso} simplesmente não faz nada quando clico.",
        "Ainda não vou cancelar, mas {recurso} tá com problema {desde} e a equipe não consegue trabalhar. Arrumem, por favor.",
    ],
    "acesso_conta": [
        "O e-mail de redefinição de senha não chega no {email}, talvez seja bug de vcs? De qualquer jeito, preciso recuperar o acesso à minha conta.",
        "A cobrança de {mes} passou normal no cartão, mas minha conta tá bloqueada depois de várias tentativas de login.",
        "Não quero cancelar nem fechar nada, só preciso trocar o e-mail de login de {email} para {email2}.",
        "Aparece {erro_login} toda vez que digito o código da verificação em duas etapas, então não consigo entrar na conta.",
        "Não é sobre entrega: a {produto} nova pede pra eu entrar na minha conta Ipê e a senha não é aceita.",
        "Podem continuar mandando as faturas pro mesmo lugar, mas quero mudar o e-mail que uso pra fazer login para {email}.",
        "Quero continuar com a assinatura {plano}, só perdi o app autenticador e preciso que resetem a verificação em duas etapas pra eu conseguir entrar.",
        "O app funciona normal no celular da minha esposa; só a minha conta ({usuario}) que não aceita mais a senha.",
    ],
    "entrega": [
        "Não quero devolver nada, só quero saber onde tá o pedido {pedido} — o rastreio não muda desde {desde_dia}.",
        "O rastreio diz entregue {quando}, mas o pacote nunca chegou, então não tenho nem o que trocar ou devolver.",
        "O pagamento foi aprovado e a cobrança já caiu no cartão, mas o pedido {pedido} continua 'em processamento' depois de {n} dias.",
        "A página de rastreio do app tá dando erro, mas isso nem importa — só me digam quando o pedido {pedido} chega.",
        "O pedido {pedido} era pra ter chegado {quando}. Não quero reembolso, ainda quero a {produto} — cadê ela?",
        "Só um dos dois volumes do pedido {pedido} chegou; o rastreio do segundo não anda desde {desde_dia}.",
        "Meu pacote do pedido {pedido} voltou pro remetente porque não acharam o endereço. Podem reenviar para {endereco}?",
        "Não é problema de cobrança, o valor tá certo — só preciso alterar o endereço de entrega do pedido {pedido} para {endereco} antes de sair pra entrega.",
    ],
    "troca_devolucao": [
        "O pacote chegou no prazo, sem problema com a entrega — mas a {produto} veio quebrada. Quero uma substituição.",
        "Mandei a {produto} de volta faz {n} dias e os Correios confirmaram a entrega no armazém de vcs. Quando sai meu reembolso de {valor}?",
        "Não tem defeito nenhum e funciona direitinho, eu que pedi errado — quero trocar a {produto} {variante}.",
        "O rastreio diz entregue e sim, recebi — mas a {produto} veio na cor errada. Como faço a troca?",
        "Vou continuar com a assinatura {plano}, só quero devolver a {produto} que comprei à parte.",
        "A {produto} parou de funcionar depois de {n} dias e prefiro devolver do que ficar tentando configurar. Como abro a devolução?",
        "Não é contestação de cobrança, o valor tava certo — só não recebi o reembolso da {produto} que devolvi há {n} dias.",
        "Não é bug: a {produto} funciona, mas chegou com um risco enorme na frente, então quero trocar.",
    ],
    "duvida_produto": [
        "Não é bug não, só quero saber se a {produto} funciona com {plataforma} antes de comprar.",
        "Antes de fechar o pedido: tem a {produto} em estoque? E ela vem com o kit de instalação?",
        "{ja_tenho}",
        "Já existe algum jeito de {capacidade_q} no app, ou ainda não tem?",
        "A {produto} é compatível com {plataforma}? Não queria comprar e depois ter que devolver.",
        "Quanto ficaria passar nossa equipe de {assentos} pessoas do {plano_baixo} pro {plano_alto}? Só pesquisando por enquanto, sem mexer na cobrança ainda.",
        "Não tô pensando em cancelar nem trocar de plano agora — só queria saber se o {plano_alto} inclui {recurso_plano} ou se é cobrado à parte.",
        "A {produto} precisa de assinatura ou funciona sem pagar mensalidade?",
    ],
    "cancelamento": [
        "Não tem nada de errado com a cobrança, a gente só não precisa mais da ferramenta — cancelem nossa assinatura {plano}.",
        "{App} tá cheio de bug faz semanas e cansei. Cancelem minha assinatura {plano} hoje mesmo.",
        "Desativem a renovação automática antes de {desde_dia}, não quero ser cobrado de novo.",
        "Ainda consigo entrar normal, mas quero que {conta_ref2} seja encerrada e os dados apagados.",
        "Não precisa mais arrumar a sincronização com o {integracao}, decidi sair. Como cancelo?",
        "Pedimos {nova_funcionalidade} faz meses e até agora nada, então vamos embora. Encerrem nosso espaço de trabalho.",
        "Não quero reembolso dos meses passados, só cancelem o plano {plano} pra não renovar em {mes}.",
        "Vou ficar com o aparelho, não vou devolver a {produto} — só quero cancelar a assinatura {plano} do app.",
    ],
    "sugestao": [
        "Não é bug, tá tudo funcionando como deveria — mas seria ótimo se a exportação também saísse em {formato}.",
        "A tela de cobrança devia deixar baixar todas as notas fiscais de uma vez num ZIP; ia poupar horas {de_quem} todo mês.",
        "Podiam adicionar a opção de entrar com {sso}? Hoje só tem e-mail e senha e é chato pra equipe.",
        "Seria legal se a página de rastreio mostrasse uma janela de horário da entrega em vez de só 'em trânsito' — já fiz {n} pedidos com vcs esse ano.",
        "Sugestão: deixar a gente pausar a assinatura {plano} por um ou dois meses em vez de ter que cancelar.",
        "O app é ótimo, sem reclamações — só queria muito {nova_funcionalidade}.",
        "Não quero reembolso nem nada, é só uma sugestão: deixem a gente abrir a troca de uma {produto} direto pelo app.",
        "Ia ajudar demais se a API tivesse um webhook de {evento}.",
        "Não vamos cancelar nem nada, mas a gente adoraria ver {nova_funcionalidade} — várias pessoas aqui comentaram.",
    ],
}

COUNTS = {
    "cobranca": 150,
    "problema_tecnico": 150,
    "acesso_conta": 150,
    "entrega": 150,
    "troca_devolucao": 150,
    "duvida_produto": 150,
    "cancelamento": 150,
    "sugestao": 150,
}


def generate(rng: random.Random) -> list[dict]:
    return merge(*[
        label_items(
            rng, label, n, TEMPLATES[label], SLOTS,
            hard_templates=HARD[label], hard_share=0.2,
            prefixes=PREFIXES, suffixes=SUFFIXES,
        )
        for label, n in COUNTS.items()
    ])

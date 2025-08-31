import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sqlite3
from sqlite3 import Error
import calendar
import time
import threading

# Configuração da página
st.set_page_config(
    page_title="Orion PMS - Sistema de Gestão Hoteleira",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injeção de CSS para interface moderna
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        color: #1a365d;
        padding-bottom: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 1.2rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-left: 5px solid #667eea;
        margin-bottom: 1.2rem;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.12);
    }
    .urgent {
        border-left: 5px solid #e53e3e !important;
    }
    .completed {
        border-left: 5px solid #38a169 !important;
    }
    .upcoming {
        border-left: 5px solid #d69e2e !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f7fafc;
        border-radius: 8px 8px 0px 0px;
        gap: 8px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
    }
    /* Animações suaves */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .fade-in {
        animation: fadeIn 0.5s ease-in-out;
    }
</style>
""", unsafe_allow_html=True)

# Inicialização do banco de dados com schema avançado
def init_advanced_db():
    conn = sqlite3.connect('orion_pms.db')
    c = conn.cursor()
    
    # Tabela de hóspedes com dados completos
    c.execute('''
        CREATE TABLE IF NOT EXISTS guests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            document_type TEXT,
            document_number TEXT UNIQUE,
            nationality TEXT,
            date_of_birth DATE,
            preferences TEXT,
            loyalty_tier TEXT DEFAULT 'Standard',
            loyalty_points INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de unidades habitacionais com atributos avançados
    c.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT,
            type TEXT NOT NULL,
            floor INTEGER,
            capacity INTEGER DEFAULT 2,
            max_capacity INTEGER DEFAULT 2,
            base_rate DECIMAL(10, 2) NOT NULL,
            status TEXT DEFAULT 'available',
            amenities TEXT,
            view_type TEXT,
            cleaning_time INTEGER DEFAULT 30,
            last_maintenance DATE,
            next_maintenance DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de reservas com campos expandidos
    c.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            confirmation_code TEXT UNIQUE,
            guest_id INTEGER,
            unit_id INTEGER,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            adults INTEGER DEFAULT 1,
            children INTEGER DEFAULT 0,
            status TEXT DEFAULT 'confirmed',
            source TEXT NOT NULL,
            rate DECIMAL(10, 2) NOT NULL,
            total_amount DECIMAL(12, 2),
            currency TEXT DEFAULT 'BRL',
            payment_status TEXT DEFAULT 'pending',
            payment_method TEXT,
            special_requests TEXT,
            notes TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guest_id) REFERENCES guests (id),
            FOREIGN KEY (unit_id) REFERENCES units (id)
        )
    ''')
    
    # Tabela de tarifas dinâmicas
    c.execute('''
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_type TEXT NOT NULL,
            date DATE NOT NULL,
            rate DECIMAL(10, 2) NOT NULL,
            min_stay INTEGER DEFAULT 1,
            max_stay INTEGER DEFAULT 30,
            stop_sell BOOLEAN DEFAULT FALSE,
            cutof_days INTEGER DEFAULT 0,
            availability INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(unit_type, date)
        )
    ''')
    
    # Tabela de tarefas de housekeeping
    c.execute('''
        CREATE TABLE IF NOT EXISTS housekeeping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            estimated_time INTEGER,
            actual_time INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES units (id)
        )
    ''')
    
    # Inserir dados iniciais
    c.execute("SELECT COUNT(*) FROM units")
    if c.fetchone()[0] == 0:
        # Unidades de exemplo
        units_data = [
            ('101', 'Standard City View', 'Standard', 1, 2, 2, 250.00, 'available', 
             'WiFi, TV, Ar-condicionado, Frigobar', 'city', 30, '2024-01-15', '2024-07-15'),
            ('102', 'Standard Garden View', 'Standard', 1, 2, 2, 280.00, 'available', 
             'WiFi, TV, Ar-condicionado, Frigobar, Varanda', 'garden', 30, '2024-01-20', '2024-07-20'),
            ('201', 'Luxo Premium', 'Luxo', 2, 3, 4, 450.00, 'available', 
             'WiFi, TV LED, Ar-condicionado, Frigobar, Varanda, Hidromassagem', 'ocean', 45, '2024-02-10', '2024-08-10'),
            ('202', 'Luxo Executivo', 'Luxo', 2, 2, 3, 420.00, 'maintenance', 
             'WiFi, TV LED, Ar-condicionado, Frigobar, Área de trabalho', 'city', 45, '2024-02-15', '2024-08-15'),
            ('301', 'Suíte Master', 'Suite', 3, 4, 6, 750.00, 'available', 
             'WiFi, TV 4K, Ar-condicionado, Frigobar, Varanda, Hidromassagem, Cozinha', 'ocean', 60, '2024-03-01', '2024-09-01')
        ]
        
        c.executemany(
            """INSERT INTO units 
            (code, name, type, floor, capacity, max_capacity, base_rate, status, amenities, view_type, cleaning_time, last_maintenance, next_maintenance) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            units_data
        )
        
        # Tarifas de exemplo
        today = date.today()
        rate_data = []
        for i in range(90):  # 90 dias de tarifas
            current_date = today + timedelta(days=i)
            for unit_type in ['Standard', 'Luxo', 'Suite']:
                # Lógica de precificação dinâmica simulada
                base_rate = 250.00 if unit_type == 'Standard' else 450.00 if unit_type == 'Luxo' else 750.00
                
                # Aumento de preço nos finais de semana
                if current_date.weekday() >= 5:  # Sábado ou Domingo
                    base_rate *= 1.3
                
                # Aumento de preço em feriados (exemplo simplificado)
                holiday_multiplier = 1.5 if current_date.month == 12 and current_date.day in [24, 25, 31] else 1.0
                base_rate *= holiday_multiplier
                
                rate_data.append((
                    unit_type, current_date, round(base_rate, 2), 
                    1, 30, False, 14, 5
                ))
        
        c.executemany(
            """INSERT INTO rates 
            (unit_type, date, rate, min_stay, max_stay, stop_sell, cutof_days, availability) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rate_data
        )
    
    conn.commit()
    return conn

# Componentes modernos da interface
def create_modern_metric_card(title, value, change=None, icon="📊", help_text=None):
    """Cria um cartão de métrica moderno"""
    change_html = ""
    if change is not None:
        change_color = "green" if change >= 0 else "red"
        change_icon = "↗️" if change >= 0 else "↘️"
        change_html = f'<span style="color: {change_color}; font-size: 0.9rem;">{change_icon} {abs(change)}%</span>'
    
    help_html = f'<span class="help-icon" title="{help_text}">ℹ️</span>' if help_text else ""
    
    card = f"""
    <div class="metric-card fade-in">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">{icon} {title}</div>
            {help_html}
        </div>
        <div style="font-size: 1.8rem; font-weight: 700; color: #2d3748;">{value}</div>
        {change_html}
    </div>
    """
    return card

def create_availability_calendar(unit_id, month, year):
    """Cria um calendário visual de disponibilidade"""
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)
    
    # Buscar reservas para esta unidade no mês
    conn = init_advanced_db()
    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])
    
    reservations = pd.read_sql_query("""
        SELECT check_in, check_out FROM reservations 
        WHERE unit_id = ? AND status IN ('confirmed', 'checked-in')
        AND ((check_in BETWEEN ? AND ?) OR (check_out BETWEEN ? AND ?))
    """, conn, params=(unit_id, start_date, end_date, start_date, end_date))
    conn.close()
    
    # Criar calendário
    fig = make_subplots(
        rows=len(month_days), cols=7,
        subplot_titles=[calendar.day_abbr[i] for i in range(7)],
        vertical_spacing=0.05,
        horizontal_spacing=0.05
    )
    
    # Adicionar dias e reservas
    for row_idx, week in enumerate(month_days):
        for col_idx, day in enumerate(week):
            if day != 0:
                current_date = date(year, month, day)
                
                # Verificar se está reservado
                is_reserved = any(
                    row['check_in'] <= current_date <= row['check_out'] 
                    for _, row in reservations.iterrows()
                )
                
                color = 'red' if is_reserved else 'green'
                
                fig.add_trace(
                    go.Scatter(
                        x=[col_idx + 0.5], y=[row_idx + 0.5],
                        text=[str(day)],
                        mode='text+markers',
                        marker=dict(size=30, color=color, opacity=0.3),
                        textfont=dict(size=14, color='black'),
                        showlegend=False
                    ),
                    row=row_idx + 1, col=col_idx + 1
                )
    
    fig.update_layout(
        height=200,
        showlegend=False,
        title=f"Disponibilidade - {calendar.month_name[month]} {year}"
    )
    
    return fig

# Módulo de Revenue Management Inteligente
class RevenueManagementSystem:
    def __init__(self):
        self.conn = init_advanced_db()
    
    def calculate_optimal_rate(self, unit_type, check_in, length_of_stay, current_occupancy):
        """Calcula a tarifa ideal baseada em múltiplos fatores"""
        # Obter tarifa base
        base_rate_df = pd.read_sql_query(
            "SELECT rate FROM rates WHERE unit_type = ? AND date = ?",
            self.conn, params=(unit_type, check_in)
        )
        
        if base_rate_df.empty:
            # Se não encontrar tarifa específica, usar base padrão
            base_rate = 250.00 if unit_type == 'Standard' else 450.00 if unit_type == 'Luxo' else 750.00
        else:
            base_rate = base_rate_df['rate'].iloc[0]
        
        # Fatores de ajuste
        day_of_week = check_in.weekday()
        season_factor = self._get_season_factor(check_in)
        demand_factor = self._get_demand_factor(check_in, length_of_stay)
        occupancy_factor = self._get_occupancy_factor(current_occupancy)
        
        # Cálculo da tarifa ideal
        optimal_rate = base_rate * season_factor * demand_factor * occupancy_factor
        
        # Ajuste para final de semana
        if day_of_week >= 5:  # Sábado ou Domingo
            optimal_rate *= 1.25
        
        return round(optimal_rate, 2)
    
    def _get_season_factor(self, date):
        """Fator de ajuste sazonal"""
        month = date.month
        if month in [12, 1, 2]:  # Alta temporada
            return 1.5
        elif month in [6, 7, 11]:  # Média temporada
            return 1.2
        else:  # Baixa temporada
            return 0.9
    
    def _get_demand_factor(self, check_in, length_of_stay):
        """Fator baseado na demanda prevista"""
        # Simulação de previsão de demanda
        days_until_checkin = (check_in - date.today()).days
        
        if days_until_checkin <= 7:
            return 1.8  # Última hora
        elif days_until_checkin <= 30:
            return 1.3  # Médio prazo
        else:
            return 1.0  # Longo prazo
    
    def _get_occupancy_factor(self, occupancy_rate):
        """Fator baseado na ocupação atual"""
        if occupancy_rate >= 0.9:
            return 1.6  # Ocupação muito alta
        elif occupancy_rate >= 0.7:
            return 1.3  # Ocupação alta
        elif occupancy_rate >= 0.5:
            return 1.1  # Ocupação média
        else:
            return 0.95  # Ocupação baixa

# Sistema de auto-atualização simplificado
class AutoRefreshSystem:
    def __init__(self, interval_minutes=2):
        self.interval = interval_minutes * 60  # Converter para segundos
        self.last_refresh = time.time()
    
    def check_refresh(self):
        current_time = time.time()
        if current_time - self.last_refresh >= self.interval:
            self.last_refresh = current_time
            return True
        return False

# Interface principal moderna
def main():
    # Inicializar sistema de auto-atualização
    if 'refresh_system' not in st.session_state:
        st.session_state.refresh_system = AutoRefreshSystem(interval_minutes=2)
    
    # Verificar se precisa atualizar
    if st.session_state.refresh_system.check_refresh():
        st.rerun()
    
    st.markdown('<h1 class="main-header">🏨 Orion PMS - Sistema de Gestão Hoteleira</h1>', unsafe_allow_html=True)
    
    # Barra lateral de navegação moderna
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 10px; color: white; margin-bottom: 20px;">
            <h2 style="margin: 0; font-size: 1.5rem;">Orion PMS</h2>
            <p style="margin: 0; font-size: 0.9rem;">Sistema de Gestão Hoteleira</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.header("Navegação")
        menu_options = ["Dashboard", "Reservas", "Hóspedes", "Unidades", "Tarifas", "Housekeeping", "Relatórios", "Revenue Management"]
        selected_menu = st.selectbox("Selecione o módulo:", menu_options, label_visibility="collapsed")
        
        st.divider()
        
        # Filtros rápidos para o dashboard
        if selected_menu == "Dashboard":
            st.subheader("Filtros Rápidos")
            date_range = st.date_input(
                "Período",
                value=(date.today(), date.today() + timedelta(days=7)),
                help="Selecione o intervalo de datas para análise"
            )
            
            unit_type_filter = st.multiselect(
                "Tipo de Unidade",
                options=["Standard", "Luxo", "Suite"],
                default=["Standard", "Luxo", "Suite"]
            )
        
        # Botão de atualização manual
        if st.button("🔄 Atualizar Dados", use_container_width=True):
            st.rerun()
    
    # Navegação entre módulos
    if selected_menu == "Dashboard":
        show_modern_dashboard()
    elif selected_menu == "Reservas":
        show_reservations_module()
    elif selected_menu == "Hóspedes":
        show_guests_module()
    elif selected_menu == "Revenue Management":
        show_revenue_management_module()
    elif selected_menu == "Unidades":
        show_units_module()
    else:
        st.info(f"Módulo {selected_menu} em desenvolvimento")

def show_modern_dashboard():
    """Dashboard moderno com métricas em tempo real"""
    st.header("📊 Dashboard de Performance")
    
    # Métricas em tempo real
    conn = init_advanced_db()
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        occupancy_rate = get_occupancy_rate()
        st.markdown(create_modern_metric_card(
            "Taxa de Ocupação", 
            f"{occupancy_rate}%", 
            change=2.5,
            icon="🏨",
            help_text="Percentual de unidades ocupadas"
        ), unsafe_allow_html=True)
    
    with col2:
        adr = get_average_daily_rate()
        st.markdown(create_modern_metric_card(
            "ADR (Diária Média)", 
            f"R$ {adr}", 
            change=3.2,
            icon="💰",
            help_text="Average Daily Rate - Receita média por unidade ocupada"
        ), unsafe_allow_html=True)
    
    with col3:
        revpar = get_revpar()
        st.markdown(create_modern_metric_card(
            "RevPAR", 
            f"R$ {revpar}", 
            change=1.8,
            icon="📈",
            help_text="Revenue Per Available Room - Receita por unidade disponível"
        ), unsafe_allow_html=True)
    
    with col4:
        arrivals = get_today_arrivals()
        st.markdown(create_modern_metric_card(
            "Check-ins Hoje", 
            str(arrivals), 
            change=-5.0,
            icon="🚪",
            help_text="Hóspedes previstos para check-in hoje"
        ), unsafe_allow_html=True)
    
    # Gráficos de performance
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Ocupação por Tipo de Unidade")
        fig = px.bar(
            get_occupancy_by_unit_type(),
            x='unit_type', y='occupancy_rate',
            color='unit_type',
            labels={'unit_type': 'Tipo de Unidade', 'occupancy_rate': 'Taxa de Ocupação (%)'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Previsão de Receita - Próximos 7 Dias")
        revenue_data = get_revenue_forecast()
        fig = px.line(
            revenue_data,
            x='date', y='projected_revenue',
            labels={'date': 'Data', 'projected_revenue': 'Receita Projetada (R$)'},
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Mapa de calor de disponibilidade
    st.subheader("Calendário de Disponibilidade")
    selected_unit = st.selectbox("Selecione a unidade:", get_available_units())
    if selected_unit:
        today = date.today()
        fig = create_availability_calendar(selected_unit, today.month, today.year)
        st.plotly_chart(fig, use_container_width=True)

def show_revenue_management_module():
    """Módulo avançado de Revenue Management"""
    st.header("💰 Revenue Management System")
    
    rms = RevenueManagementSystem()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Simulação de Precificação")
        unit_type = st.selectbox("Tipo de Unidade", ["Standard", "Luxo", "Suite"])
        check_in = st.date_input("Data de Check-in", min_value=date.today())
        length_of_stay = st.slider("Noites", 1, 30, 3)
        current_occupancy = st.slider("Ocupação Atual (%)", 0, 100, 75) / 100
        
        optimal_rate = rms.calculate_optimal_rate(unit_type, check_in, length_of_stay, current_occupancy)
        
        st.metric("Tarifa Ideal Recomendada", f"R$ {optimal_rate:.2f}")
    
    with col2:
        st.subheader("Análise de Mercado")
        st.info("Funcionalidade em desenvolvimento: Integração com dados de concorrência")
        
        # Gráfico de tendência de preços
        price_trend_data = get_price_trend_data()
        fig = px.line(
            price_trend_data,
            x='date', y='rate',
            color='unit_type',
            title='Tendência de Preços por Tipo de Unidade',
            labels={'date': 'Data', 'rate': 'Tarifa (R$)'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Recomendações estratégicas
    st.subheader("Recomendações Estratégicas")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **📈 Aumentar Tarifas**
        - Fim de semana com alta demanda
        - Aumento recomendado: 15-20%
        """)
    
    with col2:
        st.warning("""
        **🎯 Promoção Sugerida**
        - Dias de baixa ocupação
        - Desconto de 10% para estadias > 3 noites
        """)
    
    with col3:
        st.success("""
        **🛑 Stop Sell**
        - Unidades Luxo esgotadas para datas específicas
        - Aplicar restrições de chegada/partida
        """)

def show_reservations_module():
    """Módulo de gestão de reservas"""
    st.header("📋 Gestão de Reservas")
    
    tab1, tab2, tab3 = st.tabs(["Nova Reserva", "Reservas Existentes", "Calendário"])
    
    with tab1:
        st.subheader("Criar Nova Reserva")
        st.info("Funcionalidade em desenvolvimento")
    
    with tab2:
        st.subheader("Reservas Existentes")
        st.info("Funcionalidade em desenvolvimento")
    
    with tab3:
        st.subheader("Visualização em Calendário")
        st.info("Funcionalidade em desenvolvimento")

def show_guests_module():
    """Módulo de gestão de hóspedes"""
    st.header("👥 Gestão de Hóspedes")
    st.info("Funcionalidade em desenvolvimento")

def show_units_module():
    """Módulo de gestão de unidades"""
    st.header("🏠 Gestão de Unidades Habitacionais")
    
    conn = init_advanced_db()
    units_df = pd.read_sql_query("SELECT * FROM units", conn)
    conn.close()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Unidades Cadastradas")
        display_df = units_df[['code', 'name', 'type', 'status', 'base_rate']].copy()
        st.dataframe(display_df, use_container_width=True)
    
    with col2:
        st.subheader("Status das Unidades")
        status_counts = units_df['status'].value_counts()
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Distribuição por Status"
        )
        st.plotly_chart(fig, use_container_width=True)

# Funções auxiliares para dados (implementações simplificadas)
def get_occupancy_rate():
    return 78.5  # Simulado

def get_average_daily_rate():
    return 345.75  # Simulado

def get_revpar():
    return 271.36  # Simulado

def get_today_arrivals():
    return 12  # Simulado

def get_occupancy_by_unit_type():
    return pd.DataFrame({
        'unit_type': ['Standard', 'Luxo', 'Suite'],
        'occupancy_rate': [82.3, 74.6, 65.2]
    })

def get_revenue_forecast():
    dates = [date.today() + timedelta(days=i) for i in range(7)]
    return pd.DataFrame({
        'date': dates,
        'projected_revenue': [12500, 13200, 14500, 15200, 14800, 16200, 17500]
    })

def get_available_units():
    return ["101", "102", "201", "202", "301"]

def get_price_trend_data():
    dates = [date.today() + timedelta(days=i) for i in range(30)]
    data = []
    for unit_type in ["Standard", "Luxo", "Suite"]:
        base_rate = 250 if unit_type == "Standard" else 450 if unit_type == "Luxo" else 750
        for i, d in enumerate(dates):
            # Variação de preço simulada
            variation = np.sin(i / 3) * 0.2 + 1
            data.append({
                'date': d,
                'unit_type': unit_type,
                'rate': base_rate * variation
            })
    return pd.DataFrame(data)

if __name__ == "__main__":
    main()
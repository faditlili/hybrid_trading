import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import requests
from requests.auth import HTTPBasicAuth

# دالة برمجية لجلب البيانات من سيرفر Render الخلفي بأمان
def fetch_dashboard_data(backend_url, username, password):
    if not backend_url or not username or not password:
        return (
            "⚠️ الرجاء إدخال رابط السيرفر وبيانات تسجيل الدخول أولاً.", 
            go.Figure(), 
            pd.DataFrame(), 
            pd.DataFrame()
        )
    
    # تنظيف الرابط للتأكد من خلوه من الفراغات
    backend_url = backend_url.strip().rstrip('/')
    status_url = f"{backend_url}/dashboard/status"
    trades_url = f"{backend_url}/dashboard/trades"
    decisions_url = f"{backend_url}/dashboard/decisions"
    
    try:
        auth = HTTPBasicAuth(username, password)
        
        # 1. جلب البيانات الأساسية للحساب والصفقات المفتوحة بالتوازي
        status_res = requests.get(status_url, auth=auth, timeout=10)
        if status_res.status_code != 200:
            return f"❌ خطأ في الاتصال: السيرفر أرجع رمز الاستجابة {status_res.status_code}", go.Figure(), pd.DataFrame(), pd.DataFrame()
            
        status_data = status_res.json()
        account = status_data.get("account", {})
        positions = status_data.get("positions", [])
        engine_status = status_data.get("engine", {})
        
        # 2. جلب سجل الصفقات المغلقة
        trades_res = requests.get(trades_url, auth=auth, timeout=10)
        trades_list = trades_res.json() if trades_res.status_code == 200 else []
        
        # 3. جلب سجل قرارات البوت والـ AI
        decisions_res = requests.get(decisions_url, auth=auth, timeout=10)
        decisions_list = decisions_res.json() if decisions_res.status_code == 200 else []

        # --- معالجة الحسابات الإحصائية والمالية الفورية ---
        balance = account.get("balance", 0.0)
        equity = account.get("equity", 0.0)
        realized_pnl = account.get("realized_pnl", 0.0)
        
        # حساب نسبة النجاح (Win Rate)
        total_trades = len(trades_list)
        winning_trades = sum(1 for t in trades_list if t.get("pnl", 0) > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # صياغة بطاقة الحالة النصية الملخصة للمستثمر
        summary_text = f"""
        ### 📊 ملخص أداء المحفظة الافتراضية (Live Paper Statistics)
        * **إجمالي السيولة الحالية (Equity):** ${equity:,.2f}
        * **الرصيد المتاح (Available Balance):** ${balance:,.2f}
        * **صافي الأرباح المحققة (Realized PnL):** ${realized_pnl:,.2f}
        * **إجمالي الصفقات المغلقة:** {total_trades} صفقة
        * **نسبة نجاح الصفقات (Win Rate):** {win_rate:.1f}%
        * **حالة المحرك الرئيسي:** {"🟢 يعمل بنشاط" if engine_status.get("running") else "🔴 متوقف مؤقتاً"}
        * **آخر فحص تلقائي للسوق:** {engine_status.get("last_scan", "لا يوجد بيانات بعد")}
        """
        
        # --- بناء الرسم البياني التفاعلي لمنحنى نمو رأس المال (Equity Curve) ---
        fig = go.Figure()
        if total_trades > 0:
            # ترتيب الصفقات زمنياً لرسم المنحنى بدقة
            df_trades = pd.DataFrame(trades_list).sort_values("id")
            df_trades["cumulative_pnl"] = df_trades["pnl"].cumsum()
            # افتراض نقطة انطلاق للمحفظة قبل الأرباح
            starting_balance = equity - realized_pnl
            df_trades["equity_curve"] = starting_balance + df_trades["cumulative_pnl"]
            
            fig.add_trace(go.Scatter(
                x=list(range(1, len(df_trades) + 1)),
                y=df_trades["equity_curve"],
                mode='lines+markers',
                name='Equity Growth',
                line=dict(color='#00ff88', width=3),
                marker=dict(size=6)
            ))
        else:
            # رسم خط ثابت للمحفظة الجديدة في حال غياب صفقات مغلقة
            fig.add_trace(go.Scatter(x=[0, 1], y=[balance, balance], mode='lines', name='No Trades Yet', line=dict(dash='dash', color='#888888')))
            
        fig.update_layout(
            title="📈 منحنى نمو السيولة الإجمالية للمحفظة (Equity Curve History)",
            xaxis_title="عدد الصفقات المتتالية",
            yaxis_title="قيمة المحفظة بالدولار ($)",
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        # --- تحويل الجداول لبيانات منظمة سهلة القراءة ---
        # 1. جدول الصفقات المفتوحة حالياً
        if positions:
            df_pos = pd.DataFrame(positions)[["symbol", "entry", "qty", "stop", "target", "opened"]]
            df_pos["opened"] = pd.to_datetime(df_pos["opened"], unit='s').dt.strftime('%Y-%m-%d %H:%M')
            df_pos.columns = ["الرمز", "سعر الدخول", "الكمية", "وقف الخسارة", "الهدف النهائي", "تاريخ الفتح"]
        else:
            df_pos = pd.DataFrame(columns=["لا توجد صفقات مفتوحة حالياً في السوق"])

        # 2. جدول سجل القرارات الفنية والذكاء الاصطناعي
        if decisions_list:
            df_dec = pd.DataFrame(decisions_list)[["symbol", "action", "score", "created"]]
            df_dec["created"] = pd.to_datetime(df_dec["created"], unit='s').dt.strftime('%H:%M:%S')
            df_dec.columns = ["العملة", "القرار الصادر", "النقاط الفنية", "الوقت"]
        else:
            df_dec = pd.DataFrame(columns=["سجل القرارات فارغ"])
            
        return summary_text, fig, df_pos, df_dec
        
    except Exception as e:
        return f"❌ فشل الاتصال بالخادم: {str(e)}", go.Figure(), pd.DataFrame(), pd.DataFrame()

# --- بناء الهيكل الخارجي لواجهة العرض بأسلوب سمارت الاحترافي (Dark Theme) ---
with gr.Blocks(theme=gr.themes.Monochrome(), css="footer {visibility: hidden}") as demo:
    gr.Markdown("""
    # 🤖 AI QUANT 4.0 - لوحة المراقبة التفاعلية الذكية
    واجهة عرض رسومية متطورة وقارئة للبيانات الفورية، محمية بالكامل وتعمل داخل متصفحك عبر **Gradio Lite Wasm** للاتصال بخادمك السحابي.
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            url_input = gr.Textbox(label="رابط سيرفر Render الخلفي (Backend URL)", placeholder="https://onrender.com", type="text")
        with gr.Column(scale=1):
            user_input = gr.Textbox(label="اسم المستخدم (Username)", placeholder="admin", type="text")
        with gr.Column(scale=1):
            pass_input = gr.Textbox(label="كلمة المرور (Password)", type="password")
            
    btn_refresh = gr.Button("🔄 تحديث وقراءة البيانات الحية فوراً", variant="primary")
    
    with gr.Row():
        with gr.Column(scale=1):
            summary_output = gr.Markdown("📌 الرجاء إدخال بيانات السيرفر والضغط على زر التحديث لقراءة أداء المحفظة الافتراضية.")
        with gr.Column(scale=2):
            chart_output = gr.Plot(label="منحنى نمو المحفظة الإحصائي")
            
    gr.Markdown("### 🟢 الصفقات المفتوحة حالياً في السوق التجريبي (Active Positions)")
    pos_table = gr.DataFrame()
    
    gr.Markdown("### 🧠 سجل قرارات المسح وفلاتر الذكاء الاصطناعي الأخيرة (Recent Strategy Decisions)")
    dec_table = gr.DataFrame()
    
    # ربط المكونات البرمجية بالزر لتحديث المحتويات بلحظة واحدة
    btn_refresh.click(
        fn=fetch_dashboard_data,
        inputs=[url_input, user_input, pass_input],
        outputs=[summary_output, chart_output, pos_table, dec_table]
    )

# تشغيل الواجهة الرسومية محلياً أو سحابياً
if __name__ == "__main__":
    demo.launch()

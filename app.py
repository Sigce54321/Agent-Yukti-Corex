"""Page configuration and reference-matched global styling."""
import streamlit as st
from ui.dashboard import render_dashboard

STYLE = """
<style>
:root{color-scheme:dark;--navy:#091321;--panel:#132236;--cyan:#23e7f1;--purple:#b75aeb;--text:#e6edf7;--muted:#93a5bf;--line:#31445e;}
html,body{font-family:"Segoe UI",Inter,Arial,sans-serif;}
.stApp{background:radial-gradient(ellipse at 88% 3%,#47216c35,transparent 40%),radial-gradient(ellipse at 10% 95%,#0a52652b,transparent 42%),#091321;color:var(--text);}
[data-testid="stHeader"]{background:transparent;height:2rem;}
[data-testid="stToolbar"]{top:0;}
[data-testid="stMainBlockContainer"]{max-width:1900px;padding:3rem 1.1rem .8rem;container-type:inline-size;container-name:workspace;}
[data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]{gap:.75rem;}
h1,h2,h3{color:#e9f1ff;letter-spacing:-.025em;}h1{font-size:1.6rem!important;}h2{font-size:1.05rem!important;}h3{font-size:.94rem!important;padding:.1rem 0 .5rem!important;}
[data-testid="stMain"] p,[data-testid="stMain"] li,[data-testid="stWidgetLabel"] p{font-size:.85rem;line-height:1.5;overflow-wrap:anywhere;}
[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"]{color:var(--text);}
[data-testid="stCaptionContainer"] p{font-size:.75rem;color:var(--muted);line-height:1.5;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f1829,#0a1320);border-right:1px solid #23384a;}
[data-testid="stSidebarUserContent"]{padding:1.15rem .65rem;}
[data-testid="stSidebar"] [role="radiogroup"]{gap:.35rem;}
[data-testid="stSidebar"] [role="radiogroup"] label{box-sizing:border-box;padding:.45rem .35rem;margin:0!important;border:1px solid transparent;border-radius:7px;background:transparent;width:100%;align-items:center;gap:.3rem;}
[data-testid="stSidebar"] [role="radiogroup"] label p{font-size:.8rem;white-space:normal;line-height:1.4;}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:linear-gradient(100deg,#095b6980,#63378b70);border-color:#2db9cc8c;box-shadow:inset 0 0 12px #31deed20,0 0 12px #22d3ee17;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#1b2e43;}
.side-logo{display:flex;align-items:center;gap:8px;font-weight:750;font-size:1rem;white-space:nowrap;}.side-logo svg{color:var(--cyan);filter:drop-shadow(0 0 6px #20f3f488);}.violet{color:#b66df2;}
.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:0 2px 14px;border-bottom:1px solid #23798a66;position:relative;}
.topbar:after{content:"";position:absolute;width:36%;height:1px;background:linear-gradient(90deg,transparent,var(--purple),var(--cyan),transparent);bottom:-1px;left:25%;box-shadow:0 0 12px #17f4ff;}
.wordmark{display:flex;align-items:center;gap:12px;font-size:1.6rem;font-weight:750;letter-spacing:-.045em;white-space:nowrap;}.wordmark svg{color:var(--cyan);filter:drop-shadow(0 0 8px #22ecf2aa);}
.product-tag{border:1px solid #7454aa66;background:linear-gradient(100deg,#19455b88,#482d6c77);border-radius:8px;padding:5px 11px;color:#e5d9fd;font-size:.65rem;letter-spacing:0;font-weight:500;box-shadow:inset 0 0 8px #6d4c8d33;}
.topbar-note{font-size:.6rem;letter-spacing:.12em;color:#a1b4ce;display:flex;align-items:center;gap:12px;}.avatar{display:grid;place-items:center;width:30px;height:30px;border:1px solid #8b54bc;border-radius:50%;background:#42327255;color:#bbfaff;font-size:.68rem;letter-spacing:0;}
.summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px!important;margin-bottom:22px!important;gap:12px;margin:2px 0 3px;}
.summary-card{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:12px;padding:14px;border:1px solid #3c91aa;border-radius:9px;background:linear-gradient(115deg,#123343,#1b263c 57%,#131e30);box-shadow:inset 0 1px 9px #25e5ff22,0 0 10px #24c9de19;min-width:0;box-sizing:border-box;}
.summary-card.purple{border-color:#784ba6;background:linear-gradient(115deg,#322448,#20253d 70%,#131e30);box-shadow:inset 0 1px 9px #b34be833,0 0 10px #9b3fc522;}
.metric-icon{color:var(--cyan);filter:drop-shadow(0 0 6px #1edbec55);}.purple .metric-icon{color:#d28af4;filter:drop-shadow(0 0 6px #bb5deb66);}
.metric-label{font-size:.78rem;font-weight:600;color:#ced9ed;}.metric-value{font-size:1.4rem;font-weight:750;line-height:1.4;overflow-wrap:anywhere;}.summary-card small{display:block;margin-top:4px;color:#a3b5cf;font-size:.7rem;line-height:1.4;}.summary-content{min-width:0;}
.st-key-dashboard_grid [data-testid="stVerticalBlock"]{gap:.75rem;}
.st-key-dashboard_grid [data-testid="stColumn"],.st-key-dashboard_grid [data-testid="stLayoutWrapper"]{min-width:0;}
.st-key-repository_panel,.st-key-issue_panel,.st-key-location_panel,.st-key-patch_panel,.st-key-challenger_panel,.st-key-verification_panel,.st-key-agents_panel,.st-key-timeline_panel,.st-key-passport_panel{background:linear-gradient(130deg,#122337,#202b4288)!important;border:1px solid #324a65!important;border-radius:9px!important;box-shadow:inset 0 1px 10px #7db6ff0d,0 3px 14px #0004!important;}
.st-key-issue_panel{border-left-color:#24c1d2!important;box-shadow:inset 0 0 16px #167c9915,0 0 9px #15dcea16!important;}
.st-key-decision_panel{border:1px solid #42e4ec!important;border-left-color:#ac59ed!important;border-radius:11px!important;background:linear-gradient(145deg,#232542,#122637 65%,#191c38)!important;box-shadow:0 0 7px #26e2ef99,inset 0 0 13px #27d9ec33,-4px 0 14px #a950d933!important;}
.st-key-decision_panel h3{color:#f0e9ff!important;}.st-key-decision_panel h3:before{content:"◇ ";color:var(--cyan);font-size:1.2rem;}
.panel-heading{display:flex;align-items:center;gap:7px;font-size:.86rem;font-weight:650;line-height:1.45;overflow-wrap:anywhere;padding:0 0 10px;margin-bottom:4px;border-bottom:1px solid #3a4b6688;}.panel-heading svg{color:#90e6ef;flex-shrink:0;}
[data-testid="stForm"]{border:0;padding:0;}.stTextInput input,.stTextArea textarea{font-size:.76rem;}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:#0d192b;color:#e3edfc;border:1px solid #41516a;border-radius:7px;}
.stButton>button,.stFormSubmitButton>button{border:1px solid #8356be;background:linear-gradient(110deg,#29314e,#302245);color:#e5e8fa;border-radius:7px;min-height:34px;font-size:.76rem;box-shadow:inset 0 0 7px #976ce622,0 0 8px #9c4add11;}
.stButton>button:hover,.stFormSubmitButton>button:hover{border-color:#6eeaf4;color:#c3fbff;box-shadow:0 0 10px #32ddec44;}
button[kind="primary"],button[kind="primaryFormSubmit"]{background:linear-gradient(110deg,#39ecf2,#00b8e5)!important;border:1px solid #43eefa!important;color:#061d2b!important;box-shadow:0 0 11px #05d5ed4d,inset 0 0 8px #b2fcff55!important;font-weight:700;}
button p{font-size:.77rem!important;}
[data-testid="stCode"]{border:1px solid #2f435e;border-radius:7px;}.stCode pre{background:#0d1728;color:#d5e3f5;font-size:.78rem!important;}.stCode code{font-size:.78rem!important;}
[data-testid="stExpander"] details{background:#101b2d;border-color:#354761;border-radius:7px;}
[data-testid="stExpander"] summary p{font-size:.8rem;}
[data-testid="stAlert"]{padding:.45rem .6rem;border:1px solid #3b678066;background:#12344744;border-radius:7px;}
[data-testid="stAlert"] p{font-size:.8rem;}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#2be7e9,#ae69ec);}
.evidence-row{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);align-items:start;gap:8px;padding:8px 0;border-bottom:1px solid #30405a66;font-size:.76rem;}.evidence-row span{color:#b0bfd5;overflow-wrap:anywhere;}.evidence-row b{font-weight:500;color:#e4ecfa;text-align:right;overflow-wrap:anywhere;min-width:0;}
.status-badge{display:inline-block;padding:3px 7px;font-size:.7rem;overflow-wrap:anywhere;line-height:1.3;border:1px solid #65739766;border-radius:20px;background:#243750;color:#c6d6ee;white-space:normal;}.status-badge.good{color:#80e4b0;border-color:#38977988;background:#183f3d;}.status-badge.bad{color:#f7a1be;border-color:#b64f7a88;background:#44213e;}
.issue-number{font-size:.85rem;font-weight:700;margin-bottom:7px;}.empty-symbol{color:#4a829e;text-align:center;padding:18px 0 12px;}
.result-callout{padding:12px 10px;background:linear-gradient(130deg,#0a3b3899,#12343166);border:1px solid #28866f99;border-radius:7px;margin-top:16px;}.result-callout b{color:#8cdec2;font-size:.72rem;}.result-callout p{font-size:.7rem;margin:8px 0 0;line-height:1.6;}
.patch-file{display:flex;align-items:center;justify-content:space-between;gap:5px;background:#101c30;border:1px solid #354964;border-radius:5px;padding:6px;font-size:.63rem;overflow-wrap:anywhere;}.diff-count{color:#67dda4;white-space:nowrap;}
.empty-diff{background:repeating-linear-gradient(180deg,#0e192b 0,#0e192b 27px,#132033 28px);padding:24px 12px;color:#8094b1;font-family:Consolas,monospace;}.empty-diff span{display:block;padding:8px 4px;font-size:.65rem;}.empty-diff span:first-child{color:#ab6b89;background:#54203922;}.empty-diff span:nth-child(2){color:#64b496;background:#14583f22;}.empty-diff p{font-size:.66rem;margin-top:28px;}
.test-row{display:flex;flex-wrap:wrap;justify-content:space-between;gap:7px;align-items:center;font-size:.75rem;padding:9px 0;border-bottom:1px solid #30405a55;}
.decision-summary{padding:3px 9px 9px;background:#0c1c2d88;border:1px solid #31516c;border-radius:7px;}
.agent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px!important;gap:10px;}.agent-card{display:flex;align-items:center;gap:8px;padding:11px 8px;background:linear-gradient(125deg,#25374f,#17293d);border:1px solid #3e506b;border-radius:6px;box-shadow:inset 0 1px 7px #98b1df11;}.agent-icon{color:#c384ed;filter:drop-shadow(0 0 5px #b968e955);}.agent-card:nth-child(even) .agent-icon{color:#40d8e2;}.agent-card{min-width:0;}.agent-card>div{min-width:0;}.agent-card b{display:block;font-size:.9rem;white-space:normal;overflow-wrap:anywhere;line-height:1.4;}.agent-card small{display:flex;align-items:center;gap:4px;color:#a3b6d1;font-size:.7rem;margin-top:5px;flex-wrap:wrap;}.activity-dot{width:5px;height:5px;background:#7285a3;border-radius:50%;}.agent-card.active{border-color:#37e6d0;box-shadow:inset 0 0 10px #19c4c633;}.active .activity-dot{background:#44e8a1;box-shadow:0 0 7px #44e8a1;}
.timeline-heading{display:flex;justify-content:space-between;align-items:start;gap:8px;}.timeline-heading .panel-heading{border:0;margin:0;}.workflow-track{display:flex;justify-content:space-between;margin:14px 0 5px;}.workflow-step{position:relative;flex:1;text-align:center;min-width:0;}.workflow-step:not(:last-child):after{content:"";position:absolute;left:calc(50% + 11px);right:calc(-50% + 11px);height:2px;top:10px;background:#31465d;}.workflow-step.earlier:after{background:#20bdbf;box-shadow:0 0 5px #29e6df55;}.step-dot{position:relative;z-index:1;display:grid;place-items:center;width:22px;height:22px;margin:0 auto 9px;border:2px solid #516481;border-radius:50%;background:#19263b;color:#8499b7;font-size:.55rem;}.earlier .step-dot{border-color:#36c5cb;color:#60d7d2;}.current .step-dot{border-color:#be73f7;background:#62378c;color:#e8c4ff;box-shadow:0 0 12px #b36bef99;}.failed .step-dot{border-color:#e0719c;color:#f5b5cb;}.workflow-step b{display:block;font-size:.72rem;font-weight:600;padding:0 4px;overflow-wrap:anywhere;}.workflow-step small{display:block;font-size:.65rem;color:#a0b2cc;margin-top:4px;overflow-wrap:anywhere;}
.system-card{padding:12px 8px;background:#122234;border:1px solid #25384f;border-radius:7px;}.system-card small{display:block;color:#8da1bd;font-size:.6rem;text-align:center;margin-top:8px;}
.circuit-art{height:110px;position:relative;overflow:hidden;opacity:.9;}.circuit-core{position:absolute;left:40px;bottom:32px;width:64px;height:52px;transform:skewY(-15deg);display:grid;place-items:center;font:bold 1.65rem Consolas,monospace;color:#34eff5;background:linear-gradient(140deg,#143a49,#18213b);border:1px solid #44dbe5;box-shadow:0 0 20px #16b4dc55,inset 0 0 15px #36eaf555;}.circuit-line{position:absolute;width:1px;height:125px;left:58px;top:2px;background:linear-gradient(#ac59ed,#35e6ed);box-shadow:0 0 6px #9b55d9;transform:rotate(-18deg);}.circuit-line.b{left:96px;top:30px;height:105px;transform:rotate(15deg);background:#21869e;}
/* Layout rules target named workspace containers, rather than every Streamlit block. */
.st-key-evidence_grid{container-type:inline-size;container-name:evidence;}
.st-key-dashboard_grid :is(.panel-heading,.timeline-heading,.topbar,.patch-file){min-width:0;flex-wrap:wrap;}
.st-key-dashboard_grid .panel-heading span{min-width:0;overflow-wrap:anywhere;}
.st-key-dashboard_grid :is(button,summary){white-space:normal;overflow-wrap:anywhere;}
.st-key-dashboard_grid button{height:auto;min-height:2.4rem;padding:.45rem .65rem;}
.st-key-dashboard_grid button p{font-size:.83rem!important;line-height:1.4;}
.st-key-dashboard_grid :is(input,textarea){min-width:0;font-size:.82rem;}
.st-key-dashboard_grid :is(h2,h3){line-height:1.4;font-size:1rem!important;overflow-wrap:anywhere;}
.st-key-dashboard_grid [data-testid="stCode"]{max-width:100%;min-width:0;overflow:auto;}
.st-key-dashboard_grid :is(.status-badge,.agent-icon,.metric-icon){flex-shrink:0;}
.st-key-dashboard_grid .result-callout p{font-size:.8rem;}
.st-key-dashboard_grid .patch-file{font-size:.75rem;line-height:1.5;}
.st-key-dashboard_grid .decision-summary{padding:4px 10px 10px;}
.timeline-heading{flex-wrap:wrap;}.timeline-heading>.status-badge{max-width:100%;}
.topbar,.wordmark{flex-wrap:wrap;min-width:0;}.wordmark{white-space:normal;}
.workspace-empty{max-width:48rem;margin:clamp(1rem,4vh,3rem) auto;padding:clamp(1rem,3vw,2.5rem);text-align:center;}
.workspace-empty .empty-page-icon{color:var(--cyan);margin-bottom:1rem;}
.workspace-empty .empty-page-label{font-size:.8rem;color:#b580e8;letter-spacing:.08em;}
.workspace-empty h2{font-size:1.4rem!important;margin:.6rem 0;}
.workspace-empty p{color:#b6c7df;font-size:.9rem;line-height:1.7;}
/* Native Streamlit columns own the layout. Only stack them on narrow content;
   no CSS grid replacement or positional rules compete with their proportions. */
[data-testid="stSidebar"][aria-expanded="true"]{width:clamp(11rem,14vw,12rem)!important;min-width:11rem!important;max-width:12rem!important;}
.st-key-dashboard_grid [data-testid="stElementContainer"]{min-width:0;max-width:100%;}
.st-key-dashboard_grid :is(.status-badge,.patch-file,.result-callout,.agent-card){max-width:100%;box-sizing:border-box;}
.st-key-dashboard_grid .status-badge{min-width:0;flex-shrink:1;}
.summary-grid,.summary-card,.summary-content,.agent-grid{min-width:0;max-width:100%;}
.summary-card :is(.metric-label,small){overflow-wrap:anywhere;}
.side-logo{white-space:normal;overflow-wrap:anywhere;}.side-logo svg,.metric-icon svg,.agent-icon svg{flex-shrink:0;display:block;}
.st-key-decision_panel{margin-top:.5rem;}
.st-key-decision_panel .decision-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr));gap:0 1rem;box-sizing:border-box;max-width:100%;}
.st-key-decision_panel :is(button,textarea){max-width:100%;white-space:normal;overflow-wrap:anywhere;}
.st-key-location_panel .result-callout{margin-top:6px;}
.st-key-timeline_panel{container-type:inline-size;container-name:timeline;}
@container timeline (max-width:520px){
 .workflow-track{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px 8px;}
 .workflow-step:after{display:none;}
}
@container evidence (max-width:600px){
 .st-key-evidence_grid [data-testid="stHorizontalBlock"]:has(.st-key-patch_panel){flex-wrap:wrap;}
 .st-key-evidence_grid [data-testid="stHorizontalBlock"]:has(.st-key-patch_panel)>[data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important;min-width:0;}
}
@container workspace (max-width:900px){
 .summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
 .topbar-note{display:none;}
 .st-key-dashboard_grid [data-testid="stHorizontalBlock"]:has(.st-key-repository_panel){flex-wrap:wrap;}
 .st-key-dashboard_grid [data-testid="stHorizontalBlock"]:has(.st-key-repository_panel)>[data-testid="stColumn"]{flex:1 1 100%!important;width:100%!important;min-width:0;}
}
@container workspace (max-width:680px){
 .product-tag{display:none;}.wordmark{font-size:1.25rem;}
 .summary-card{padding:10px;gap:8px;}.metric-value{font-size:1.05rem;}
}
</style>
"""


def main():
    st.set_page_config(page_title="YuktiC-oreX | Repair workspace", page_icon="🔬", layout="wide", initial_sidebar_state="expanded")
    st.markdown(STYLE, unsafe_allow_html=True)
    render_dashboard()


if __name__ == "__main__":
    main()

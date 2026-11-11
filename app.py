import streamlit as st

from ui.dashboard import render_dashboard


def main():
    st.set_page_config(
        page_title="YuktiC-oreX",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    with st.sidebar:
        st.title("YuktiC-oreX")
        st.caption("Autonomous Bug Repair Platform")

        st.markdown("---")

        st.markdown("### Workflow")
        st.write("1. Submit GitHub issue")
        st.write("2. Analyze and locate bug")
        st.write("3. Generate proposed fix")
        st.write("4. Verify using Docker")
        st.write("5. Review and approve")
        st.write("6. Create GitHub Pull Request")

        st.markdown("---")
        st.caption("Human approval required before PR creation.")

    render_dashboard()


if __name__ == "__main__":
    main()
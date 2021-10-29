import streamlit as st


# import all chapters
from skgstat_uncertainty.api import API
from skgstat_uncertainty.chapters.data_manage import main_app as data_manager
from skgstat_uncertainty.chapters.variogram import main_app as vario_app
from skgstat_uncertainty.chapters.model_fitting import main_app as fit_app
from skgstat_uncertainty.chapters.kriging import main_app as kriging_app
from skgstat_uncertainty.chapters.model_compare import main_app as compare_app


# define the different chapters
CHAPTERS = {
    'data': 'Data Manager',
    'variogram': 'Variogram estimation',
    'model': 'Theoretical model fitting',
    'kriging': 'Model application - Kriging',
    'compare': 'Results - Compare Kriging'
}

def navigation(container=st) -> str:
    page = container.selectbox(
        'Navigation',
        options=list(CHAPTERS.keys()),
        format_func=lambda k: CHAPTERS.get(k)
    )
    return page


def main_app():
    # some page settings
    st.set_page_config('Uncertainty by hydrocode', layout='wide')

    # create an expander for the navigation
    navigation_expander = st.sidebar.expander('NAVIGATION')
    page_name = navigation(container=navigation_expander)

    # create an API instance
    # DEV - TODO: read out the cookie and set a specific database here
    api = API()

    try:
        if page_name == 'data':
            data_manager(api=api)
        elif page_name == 'variogram':
            vario_app(api=api)
        elif page_name == 'model':
            fit_app(api=api)
        elif page_name == 'kriging':
            kriging_app(api=api)
        elif page_name == 'compare':
            compare_app(api=api)
    except Exception as e:
        error_exapnder = st.expander('DEBUG', expanded=True)
        error_exapnder.title('Unallowed action')
        error_exapnder.markdown('There was an error occuring. This might happen due to running chapters without finishing the previous ones. You can inspect the error below')
        error_exapnder.exception(e)
    # done, stop streamlit
    st.stop()


if __name__ == '__main__':
    main_app()

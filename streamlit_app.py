from typing import Union
import streamlit as st
import extra_streamlit_components as stx
import os
import json
import shutil
import time
import glob
import threading
from random import choice
from string import ascii_letters
from datetime import datetime as dt, timedelta as td


# import all chapters
from skgstat_uncertainty.api import API
from skgstat_uncertainty.components import data_selector
from skgstat_uncertainty.chapters.data_manage import main_app as data_manager, sample_dense_data
from skgstat_uncertainty.chapters.variogram import main_app as vario_app
from skgstat_uncertainty.chapters.model_fitting import main_app as fit_app
from skgstat_uncertainty.chapters.kriging import main_app as kriging_app
from skgstat_uncertainty.chapters.model_compare import main_app as compare_app


# define the different chapters
ALL_CHAPTERS = {
    'home': 'Home - Start Page',
    'data': 'Data Manager',
    'sample': 'Subsample existing data',
    'variogram': 'Variogram estimation',
    'model': 'Theoretical model fitting',
    'kriging': 'Model application - Kriging',
    'compare': 'Results - Compare Kriging'
}


CONSENT_TEXT = """This application stores an randomly generated string into your browsers cookies.
This enables the application to identify your browser and load the correct data from the database.
Without this cookie, the application does not work, and you need to leave this website.
The id generated for you is: `{user_id}`.

Furthermore, you can accept or decline the sharing of anonymous usage statistics and the storage of 
a personalized database connection. This is optional, but allows custom data upload. Otherwise, 
you can only use the shared database version, which will be resetted frequently.
Personal database copies are persisted for 14 days without login.
"""


WELCOME = """
This application is built on top of SciKit-GStat and GSTools. You can use prepared data-samples or 
upload your own data to propagate uncertainties into variogram estimations and then fit various 
models to the confidence interval of the uncertain experimental variogram. The last chapter gives
you the opportunity to evaluate uncertainties resulting from the procedure.
"""


def navigation(container=st) -> str:
    can_upload = st.session_state.get('skg_opts', {}).get('can_upload', False)
    if can_upload:
        CHAPTERS = {k: v for k, v in ALL_CHAPTERS.items() if k != 'sample'}
    else:
        CHAPTERS = {k: v for k, v in ALL_CHAPTERS.items() if k != 'data'}

    page = container.selectbox(
        'Navigation',
        options=list(CHAPTERS.keys()),
        format_func=lambda k: CHAPTERS.get(k)
    )
    return page


def index() -> None:
    st.title('Index page')
    st.markdown(WELCOME)
    st.json(st.session_state.get('skg_opts'))
    
    st.stop()


def reset():
    st.session_state.clear()
    st.experimental_rerun()
    raise st.script_runner.RerunException(st.script_request_queue.RerunData(None))


def coookie_consent():
    st.title('Consent')
    user_id = ''.join(choice(ascii_letters) for _ in range(24))
    st.markdown(CONSENT_TEXT.format(user_id=user_id))

    # load the BASE_DATA
    with open(os.path.join(os.path.dirname(__file__), 'BASE_DATA.json'), 'r') as f:
        BASE_DATA = json.load(f)
     
    base_data = st.selectbox('DATABASE', options=list(BASE_DATA.keys()), format_func=lambda k: BASE_DATA.get(k))

    l, r, _ = st.columns((1,1,8))
    accept = l.button('ACCEPT')
    decline = r.button('DECLINE')
    
    if accept or decline:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
        
        if accept and base_data != 'plain':
            shutil.copy(os.path.join(path, f'{base_data}.db'), os.path.join(path, f'a_{user_id}.db'))
        
        # set info dict
        info = {
            'data_path': path,
            'db_name': f'a_{user_id}.db' if accept else 'shared.db',
            'share': accept,
            'can_upload': accept and base_data == 'plain'
        }

        mng = stx.CookieManager()
        mng.set('skg_opts', json.dumps(info), expires_at=dt.now() + td(days=14 if accept else 1))
        st.session_state.skg_opts = info
        with st.spinner('saving'):
            time.sleep(0.5)

        reset()
    else:
        st.stop()


def login():
    pass


def cleanup_files(api: API) -> None:
    # get all files
    data_path = api._kwargs.get('data_path', os.path.join(os.path.dirname(__file__), 'data'))
    files = glob.glob(os.path.join(data_path, 'a_*.db'))

    # check each file:
    for file in files:
        mod_date = dt.fromtimestamp(os.path.getmtime(file))
        if dt.now() > mod_date + td(days=14):
            os.remove(file)


def handle_session() -> str:
    opts = st.session_state.get('skg_opts')
    
    # no opts set, so load cookie consent
    if opts is None:
        mng = stx.CookieManager()
        time.sleep(0.5)
        all_cookies = mng.get_all()
        if all_cookies is None:
            all_cookies = {}
        
        # get the opts
        if 'skg_opts' in all_cookies:
            st.session_state.skg_opts = all_cookies['skg_opts']
            return all_cookies['skg_opts']
        else:
            # handle consent
            coookie_consent()

    else:
        # return the options
        return opts    
    

def main_app():
    # some page settings
    st.set_page_config('Uncertainty by hydrocode', layout='wide')

    #    default_opts = {'data_path': os.path.join(os.path.dirname(__file__), 'data'), 'db_name': f'shared.db', 'share': False}

    opts = handle_session()

    # create an expander for the navigation
    # navigation_expander = st.sidebar.expander('NAVIGATION')
    # page_name = navigation(container=navigation_expander)
    page_name = navigation(container=st.sidebar)

    # create an API instance
    api = API(**opts)

    # check if cleanup already ran in this session
    if not st.session_state.did_cleanup:
        # create a thread for cleanup
        thread = threading.Thread(target=cleanup_files, args=api)
        thread.start()
        st.session_state.did_cleanup = True

    try:
        if page_name == 'home':
            index()
        elif page_name == 'data':
            data_manager(api=api)
        elif page_name == 'sample':
            dataset = data_selector(api=api, stop_with='data', data_type='field')
            sample_dense_data(dataset=dataset, api=api)
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
    

if __name__ == '__main__':
    main_app()

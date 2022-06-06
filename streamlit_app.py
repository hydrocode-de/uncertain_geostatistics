from typing import Union
import streamlit as st
import os
import json
import shutil
import time
import glob
import threading
import requests
from random import choice
from string import ascii_letters
from datetime import datetime as dt, timedelta as td

import extra_streamlit_components as stx
import skgstat as skg
import gstools as gs
from google.cloud import firestore
from google.oauth2.credentials import Credentials


# import all chapters
from skgstat_uncertainty.api import API
from skgstat_uncertainty.components import data_selector
from skgstat_uncertainty.chapters.data_manage import main_app as data_manager, sample_dense_data
from skgstat_uncertainty.chapters.variogram import main_app as vario_app
from skgstat_uncertainty.chapters.model_fitting import main_app as fit_app
from skgstat_uncertainty.chapters.kriging import main_app as kriging_app
from skgstat_uncertainty.chapters.model_simulation import main_app as simulation_app
from skgstat_uncertainty.chapters.model_compare import main_app as compare_app


# define the different chapters
ALL_CHAPTERS = {
    'home': 'Home - Start Page',
    'data': 'Data Manager',
    'sample': 'Subsample existing data',
    'variogram': 'Variogram estimation',
    'model': 'Theoretical model fitting',
    'kriging': 'Model application - Kriging',
    'simulation': 'Model application - Simulation',
    'compare': 'Results - Compare Kriging',
    'code_ref': 'Help - Code Reference'
}


CONSENT_TEXT = """This application stores an randomly generated string into your browsers cookies.
This enables the application to identify your browser and load the correct data from the database.
Without this cookie, the application does not work, and you need to leave this website.
The id generated for you is: `{user_id}`. You can view and delete the cookie at any time from the browser.
Additionally, the HOME page of this application will expose the stored content transparently.

Furthermore, you can accept or decline the sharing of anonymous usage statistics and the storage of 
a personalized database connection. This is optional, but allows custom data upload. Otherwise, 
you can only use the shared database version, which will be resetted frequently.
Personal database copies are persisted for 14 days without login.
"""


WELCOME = """
This application is built on top of SciKit-GStat and GSTools. You can use prepared data-samples or 
upload your own data to propagate uncertainties into variogram estimations and then fit various 
models to the confidence interval of the uncertain experimental variogram. The last chapter gives
you the opportunity to evaluate uncertainties resulting from this procedure.
"""

ATTRIBUTIONS = [
    {
        "md": "### SciKit-GStat\nThe core package used for estimating variograms. Cite this always.",
        "attribution": "Mälicke, M.: SciKit-GStat 1.0: a SciPy-flavored geostatistical variogram estimation toolbox written in Python, Geosci. Model Dev., 15, 2505–2532, https://doi.org/10.5194/gmd-15-2505-2022, 2022."
    },
    {
        "md": "### GSTools\nPowerful geostatistical libary, used to perform Kriging. Cite this always.",
        "attribution": "Müller, S., Schüler, L., Zech, A., and Heße, F.: GSTools v1.3: a toolbox for geostatistical modelling in Python, Geosci. Model Dev., 15, 3161–3182, https://doi.org/10.5194/gmd-15-3161-2022, 2022."
    },
    {
        "md": "### Plotly\nNext generation plotting library - used for all plots. You need to cite this in case you use screenshots or downloads",
        "attribution": "Plotly Technologies Inc.: Collaborative data science. URL: https://plot.ly, Plotly Technologies Inc. Montréal, QC, Canada, 2015."
    },
    {
        "md": "### SciPy\nLibrary used for scientific and technical computing",
        "attribution": "Virtanen, P., Gommers, R., Oliphant, T. E., Haberland, M., Reddy, T., Cournapeau, D., … SciPy 1.0 Contributors. (2020). SciPy 1.0: Fundamental Algorithms for Scientific Computing in Python. Nature Methods, 17, 261–272. https://doi.org/10.1038/s41592-019-0686-2"
    }
]


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
    # first off - get the options from cookies
    opts = st.session_state.get('skg_opts', {})

    st.markdown('### A hydrocode application:')
    st.title('Uncertain Geostatistics')
    subtitle = st.empty()
    st.markdown(WELCOME)    
    
    st.markdown('## Attribution')
    st.markdown("In case you use anything created by this application, do not forget to cite or attribute the application and all underlying libaries:")
    attr_expander = st.expander('ATTRIBUTION', expanded=True)
    for attribution in ATTRIBUTIONS:
        attr_expander.markdown(attribution.get('md', ''))
        attr_expander.code(attribution.get('attribution', 'no resource given'))
    
    st.markdown('## Your data\nThis application is referencing your database copy using a browser cookie.')
    st.markdown('If you switch the browser, you will have to start over again. Below you can view and manage the data stored by the application.')
    
    # build the user-data expander
    auth_method = opts.get('auth_entitiy', False)
    if auth_method:
        subtitle.markdown(f"### Login: {opts.get('name', 'no name')} using {opts['auth_entitiy']}")
    
    if len(opts) > 0:
        # build the expander
        data_expander = st.expander('COOKIES', expanded=False)
        data_expander.json(opts)

        r, l, _ = data_expander.columns((1,1,5))
        del_cookie = r.button('DELETE COOKIE')
        del_all = l.button('DELETE COOKIE AND DATA')

        if del_cookie or del_all:
            # check if data should be deleted as well
            if del_all:
                fname = opts.get('db_name')
                if fname is not None and fname.startswith('a_'):
                    path = opts['data_path']
                    os.remove(os.path.join(path, fname))
                elif fname is not None and fname.startwith('u_'):
                    st.warning('This will delete your personal db on all devices, continue?')
                    con = st.button('DELETE')
                    if con:
                        path = opts['data_path']
                        os.remove(os.path.join(path, fname))
                else:
                    st.warning('Deleting non-file db connections not supported yet.')

            # do the actual cookie deletion
            mng = stx.CookieManager()
            mng.delete(cookie='skg_opts', key='cookie_delete')
            del st.session_state['skg_opts']
            

            with st.spinner('Deleting cookie...'):
                time.sleep(1.0)
                reset()


def code_reference() -> None:
    st.title('Code reference')
    st.markdown('Below, you can load the docstring for the relevant functions taken from SciKit-GStat and GSTools')

    funcs = {
        skg.Variogram.__init__: 'Variogram [SciKit-GStat]',
        gs.Krige: 'Kriging [GSTools]',
        gs.CondSRF: 'Simulation [GSTools]',
        skg.Variogram.set_bin_func: 'Variogram binning [SciKit-GStat]',
        skg.models.spherical: 'Spherical Model [SciKit-GStat]',
        skg.models.exponential: 'Exponential Model [SciKit-GStat]',
        skg.models.gaussian: 'Gaussian Model [SciKit-GStat]',
        skg.models.cubic: 'Cubic Model [SciKit-GStat]',
        skg.models.stable: 'Stable Model [SciKit-GStat]',
        skg.models.matern: 'Matérn Model [SciKit-GStat]',
        skg.estimators.matheron: 'Mathéron estimator [SciKit-GStat]',
        skg.estimators.cressie: 'Cressie-Hawkins estimator [SciKit-GStat]',
        skg.estimators.dowd: 'Dowd estimator [SciKit-GStat]',
        skg.estimators.genton: 'Genton estimator [SciKit-GStat]',
        skg.binning.even_width_lags: 'Even width binning [SciKit-GStat]',
        skg.binning.auto_derived_lags: 'Binning with auto-derived lags [SciKit-GStat]',
        skg.binning.kmeans: 'KMean binning [SciKit-GStat]',
    }

    func_name = st.selectbox('Function name', options=list(funcs.keys()), format_func=lambda k: funcs.get(k))

    st.markdown(f'## Code documentation')
    help_expander = st.expander('__doc__', expanded=True)
    help_expander.help(func_name)


def reset():
    st.session_state.clear()
    st.experimental_rerun()
    # raise st.script_runner.RerunException(st.script_request_queue.RerunData(None))


def coookie_consent(mng: stx.CookieManager):
    st.title('Consent')
    user_id = ''.join(choice(ascii_letters) for _ in range(24))
    st.markdown(CONSENT_TEXT.format(user_id=user_id))

    # load the BASE_DATA
    with open(os.path.join(os.path.dirname(__file__), 'BASE_DATA.json'), 'r') as f:
        BASE_DATA = json.load(f)
     
    base_data = st.selectbox('DATABASE', options=list(BASE_DATA.keys()), format_func=lambda k: BASE_DATA.get(k))

    l, c, r, _ = st.columns((1,1,1,7))
    accept = l.button('ACCEPT')
    decline = c.button('DECLINE')
    login(cookie_manager=mng, key='consent_login', base_data=base_data, container=r)
    
    if accept or decline:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
        
        if accept:
            shutil.copy(os.path.join(path, f'{base_data}.db'), os.path.join(path, f'a_{user_id}.db'))
        
        # set info dict
        info = {
            # 'data_path': path,
            'db_name': f'a_{user_id}.db' if accept else 'shared.db',
            'share': accept,
            'can_upload': accept,
            'did_login': False
        }

        # mng = stx.CookieManager()
        mng.set('skg_opts', json.dumps(info), expires_at=dt.now() + td(days=14 if accept else 1))
        st.session_state.skg_opts = info
        with st.spinner('saving'):
            time.sleep(0.5)

        reset()
    else:
        st.stop()


def _firebase_login(username: str, password: str, token_only: bool = False):
    # open config file
    with open(os.path.join(os.path.dirname(__file__), '.firebase.json'), 'r') as f:
        CONF = json.load(f)
    
    # get the info
    API_KEY = CONF['APIKEY']
    SIGNIN_URL = CONF['SIGNINURL'].format(apikey=API_KEY)
    PROJECT_ID = CONF['PROJECTID']

    # create details for authentication
    details = dict(
        email=username,
        password=password,
        returnSecureToken=True
    )

    # send the request
    response = requests.post(SIGNIN_URL, data=details)
    data = response.json()

    if token_only:
        return data

    # check if successful
    if 'idToken' in data:
        # create credentials
        cred = Credentials(data['idToken'], refresh_token=data.get('refreshToken'))

        # connect firestore and load user data
        db = firestore.Client(credentials=cred, project=PROJECT_ID)
        ref = db.collection('users').document(data.get('localId')).get()

        return ref.to_dict()
    else:
        raise RuntimeError(json.dumps(data))


def login(cookie_manager: stx.CookieManager, key='', base_data: str = None, container=st):
    # add the button
    if not st.session_state.get('logging_in', False):
        do_login = container.button('LOGIN', key=f'LOGIN_{key}')
    else:
        do_login = False

    # handle login if the user clicked the button
    if do_login or st.session_state.get('logging_in', False):
        st.session_state['logging_in'] = True

        with st.expander('LOGIN', expanded=True):
            with st.form('LOGIN_FORM', clear_on_submit=True):
                username = st.text_input('Username')
                password = st.text_input('Password')

                if base_data is None:
                    # load the BASE_DATA
                    with open(os.path.join(os.path.dirname(__file__), 'BASE_DATA.json'), 'r') as f:
                        BASE_DATA = json.load(f)
                    base_data = st.selectbox('DATABASE', options=list(BASE_DATA.keys()), format_func=lambda k: BASE_DATA.get(k))

                did_submit = st.form_submit_button('SEND')

                if did_submit:
                    # authenticate with firebase
                    try:
                        user_data = _firebase_login(username, password)
                    except Exception as e:
                        st.error(str(e))
                        st.stop()
                    
                    # if not stopped, the authentication was successful
                    path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'data'))
                        
                    # handle the login
                    info = {'data_path': path}
                    info.update(user_data.get('info', {}))
                    
                    # do the saving
                    with st.spinner('saving'):
                        cookie_manager.set('skg_opts', json.dumps(info), expires_at=dt.now() + td(days=30))    
                        time.sleep(0.5)

                        # if sqlite copy base data if necessary
                        if base_data != 'plain' and info.get('db_name', '').endswith('.db'):
                            if not os.path.exists(os.path.join(path, f'u_{username}.db')):
                                    shutil.copy(os.path.join(path, f'{base_data}.db'), os.path.join(path, f'u_{username}.db'))
                        
                        # handle session state
                        st.session_state.skg_opts = info
                        st.session_state['did_login'] = True
                        del st.session_state['logging_in']

                    # reset
                    reset()
            
            # cancel button
            cancel = st.button('CANCEL')
            if cancel:
                del st.session_state['logging_in']
                st.experimental_rerun()


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
            coookie_consent(mng)
    elif not opts.get('did_login', False):
        mng = stx.CookieManager()
        login(mng, key='session_handler', container=st.sidebar)
        return opts
    else:
        # return the options
        return opts    
    

def main_app(**kwargs):
    # some page settings
    st.set_page_config('Uncertainty by hydrocode', layout=kwargs.get('layout', 'wide'))

    # add the logo
    st.sidebar.image("https://firebasestorage.googleapis.com/v0/b/hydrocode-website.appspot.com/o/public%2Fhydrocode_brand.png?alt=media")

    # get the session data to identify correct database
    opts = handle_session()

    # fix paths
    data_path = kwargs.get('data_path', os.path.join(os.path.dirname(__file__), 'data'))
    opts.update({'data_path': data_path})
    
    # add navigation
    page_name = navigation(container=st.sidebar)

    # create an API instance
    api = API(**opts)

    # check if cleanup already ran in this session
    did_cleanup = st.session_state.get('did_cleanup', False)
    if not did_cleanup:
        # create a thread for cleanup
        thread = threading.Thread(target=lambda: cleanup_files(api=api))
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
        elif page_name == 'simulation':
            simulation_app(api=api)
        elif page_name == 'compare':
            compare_app(api=api)
        elif page_name == 'code_ref':
            code_reference()
    except Exception as e:
        error_exapnder = st.expander('DEBUG', expanded=True)
        error_exapnder.title('Unallowed action')
        error_exapnder.markdown('There was an error occuring. This might happen due to running chapters without finishing the previous ones. You can inspect the error below')
        error_exapnder.exception(e)
    

if __name__ == '__main__':
    import fire
    fire.Fire(main_app)

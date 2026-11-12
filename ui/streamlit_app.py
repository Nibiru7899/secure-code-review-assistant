"""Guided, local-only Case Study 4 engineering workspace."""
from urllib.parse import urlencode, quote
from datetime import datetime, timezone
import streamlit as st
from ui.client import API, APIError
from ui.presentation import local_time, OUTCOMES, diagnostic_text
from ui.components import STANDARD_NOTICE, request_error, source_preview, show_report, findings_table, downloads

STYLE = """<style>
.block-container{padding-top:1.3rem;padding-bottom:2rem;max-width:1350px}
[data-testid="stSidebar"]{background:#141922;border-right:1px solid #303846}
[data-testid="stMetric"]{background:#191f2a;border:1px solid #303846;border-radius:8px;padding:.8rem}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:#303846}
h1{font-size:1.85rem!important}h2{font-size:1.3rem!important}h3{font-size:1.05rem!important}
code,pre{font-family:Consolas,monospace!important}button{min-height:2.4rem}
@media(max-width:700px){.block-container{padding:1rem!important}h1{font-size:1.5rem!important}}
</style>"""
PAGES = ["Overview", "Repository Review", "Analyze Source", "Diagnostics", "Findings", "History & Reports"]


def go(page):
    st.session_state.next_navigation = page
    st.rerun()


def start_repository(api, repository, snapshot):
    try:
        result = api.request('/review/repository', {'repository': repository, 'snapshot': snapshot})
    except APIError as exc:
        request_error(exc, write=True)
        return
    st.session_state.repo_run = result['id']
    go('Repository Review')


@st.fragment(run_every='2s')
def repository_progress(api, repository, identifier):
    try:
        run = api.request('/repository-reviews/' + identifier + '?' + urlencode({'repository': repository}))
        n, total = len(run['results']), len(run['functions'])
        st.progress(n / total if total else 0, text=f'Reviewed {n} of {total} functions')
        st.text('Current function: ' + (run.get('current_function') or 'Preparing captured analysis'))
        created = datetime.fromisoformat(run['created'].replace('Z', '+00:00'))
        elapsed = max(0, (datetime.now(timezone.utc) - created.replace(tzinfo=created.tzinfo or timezone.utc)).total_seconds())
        st.caption(f'Elapsed: {elapsed:.1f} seconds · sequential local inference')
        counts = {key: sum(r['outcome'] == key for r in run['results']) for key in ('CANDIDATES', 'NO_SUPPORTED_FINDING', 'INSUFFICIENT_EVIDENCE', 'FAILED')}
        st.dataframe([{'Outcome': OUTCOMES[k], 'Functions': v} for k, v in counts.items()], hide_index=True, use_container_width=True)
        if run['status'] != 'RUNNING':
            st.rerun()
    except APIError as exc:
        request_error(exc)


def summary_cards(summary):
    columns = st.columns(3)
    for col, label, key in zip(columns, ('Functions reviewed', 'Candidate findings', 'Need more evidence / failed'),
        ('functions_reviewed', 'candidate_findings', None)):
        col.metric(label, summary[key] if key else summary['outcomes']['INSUFFICIENT_EVIDENCE'] + summary['outcomes']['FAILED'])
    st.caption(f'{summary["functions_discovered"]} functions discovered · {summary["total_seconds"]:.1f} seconds · {summary["functions_per_minute"] or 0:.1f} functions/minute')
    st.caption('Candidates are suggestions for human assessment. No supported finding does not mean safe code.')


def repository_dashboard(api, repository, identifier, active_snapshot):
    run = api.request('/repository-reviews/' + identifier + '?' + urlencode({'repository': repository}))
    st.subheader(OUTCOMES.get(run['status'], run['status']))
    st.caption(local_time(run['created']))
    if run['snapshot'] != active_snapshot:
        st.warning('This review uses a historical source version. Start a new review for the active index.')
    if run['status'] == 'RUNNING':
        repository_progress(api, repository, identifier)
        return
    document = api.request('/repository-reviews/' + identifier + '/report?' + urlencode({'repository': repository}))
    if run['status'] == 'INTERRUPTED':
        st.warning('The review stopped before completion. Unprocessed functions were not reviewed; start a new review explicitly.')
    summary_cards(document['summary'])
    a, b = st.columns(2)
    a.dataframe([{'Severity': k, 'Candidates': v} for k, v in document['summary']['severity'].items()], hide_index=True, use_container_width=True)
    b.dataframe([{'Category': k, 'Candidates': v} for k, v in document['summary']['category'].items()], hide_index=True, use_container_width=True)
    if run['analyzer']['status'] in ('failed', 'unavailable', 'degraded'):
        st.warning('Static-analysis coverage is limited: ' + run['analyzer']['status'] + '. See limitations before deciding.')
    with st.expander('Coverage, function outcomes and limitations'):
        st.json(document['coverage'])
        st.dataframe([{'File': r['file'], 'Function': r['function'], 'Outcome': OUTCOMES[r['outcome']]} for r in run['results']], hide_index=True)
        for item in document['limitations']:
            st.text(item)
        st.json(run['analyzer'])
    downloads(document, 'repository-' + identifier)
    rows = [entry['effective_finding'] | {'id': entry['original']['id'], 'run_id': d['run']['id'],
            'disposition': entry['disposition'], 'evidence_support': entry['evidence_support']}
            for d in document['function_reports'] for entry in d['reviewed_findings']]
    st.subheader('Review candidate findings')
    findings_table(api, rows, repository, 'repository', active_snapshot)


def analyze_source(api, repository, status, diagnostics=False):
    if diagnostics:
        st.caption('Interpret imported evidence. No log command, build, script or CI job will run.')
        mode = st.radio('Import method', ['Paste text', 'Choose local file'], horizontal=True)
        evidence_type = st.selectbox('Evidence type', ['Compiler warnings', 'Static-analysis report', 'Build log', 'Runtime log', 'CI log'])
        value = st.text_area('Diagnostic text', height=160, help='Up to 6,000 characters; larger excerpts are rejected without truncation.') if mode == 'Paste text' else st.file_uploader('Local diagnostic file', type=['txt', 'log', 'xml'])
        if mode == 'Choose local file':
            st.caption('Application limit: UTF-8 text, up to 6,000 characters. Larger input is rejected without truncation regardless of the file picker limit.')
        origin = st.text_input('Where did this evidence come from?', placeholder='For example: synthetic ECU build log', max_chars=200)
        with st.expander('Optional tool details'):
            tool = st.text_input('Tool name', placeholder='Leave blank if unknown', max_chars=100)
            version = st.text_input('Tool version', max_chars=100)
        group, task = 'Diagnostics', 'Interpret diagnostics'
    else:
        group = st.radio('What would you like to do?', ['Review', 'Explain', 'Ask a Question'], horizontal=True, key='task-group')
        if group == 'Review':
            task = st.selectbox('Review focus', ['General code review', 'Security review', 'Coding-standard / MISRA-oriented review assistance', 'Performance observations'])
        elif group == 'Explain':
            task = st.selectbox('Explanation type', ['Function Explanation', 'Module Summary', 'Dependency Summary', 'Control-Flow Summary'])
        else:
            task = 'Code Q&A'
        if 'Coding-standard' in task:
            st.info(STANDARD_NOTICE)
            st.caption('Only original/demo engineering rules are installed.')
        if task == 'Performance observations':
            st.info('Static/source-level observations only. No runtime profiling or measured speedup.')
    files = status['files']
    if not files:
        st.info('There is no captured source to select. Re-index an authorized repository containing C/C++ source.')
        return
    preferred = next((i for i, f in enumerate(files) if f.endswith(('.cpp', '.c', '.cc', '.cxx'))), 0)
    file = st.selectbox('Source file', files, index=preferred, key='analysis-file')
    units = list({(f['symbol'], f['signature']): f for f in status['functions'] if f['file'] == file}.values())
    labels = ['Whole file'] + [f'{u["symbol"]} · line {u["start_line"]} · {u["signature"]}' for u in units]
    selected = st.selectbox('Function or file scope', labels, index=1 if units else 0, key='analysis-scope', disabled=task == 'Module Summary')
    unit = units[labels.index(selected) - 1] if selected != 'Whole file' and task != 'Module Summary' else None
    source_preview(api, repository, status['snapshot'], file, unit)
    question = st.text_input('Your code question' if task == 'Code Q&A' else 'Question or focus (optional)', max_chars=1200,
                             placeholder='For example: what happens if the pointer is null?', key='question')
    selection = (repository, status['snapshot'], file, (unit or {}).get('symbol'), (unit or {}).get('signature'), task, question)
    if diagnostics:
        selection += (mode, origin, tool, version, value if mode == 'Paste text' else (value.name, value.size) if value is not None else None)
    if st.session_state.get('analysis_selection') != selection:
        st.session_state.pop('report', None)
        st.session_state.analysis_selection = selection
    button = 'Interpret evidence' if diagnostics else 'Ask about this code' if task == 'Code Q&A' else 'Explain selected code' if group == 'Explain' else 'Review selected code'
    if st.button(button, type='primary'):
        try:
            if task == 'Code Q&A' and not question.strip():
                raise ValueError('Enter your code question before continuing.')
            if task == 'Function Explanation' and unit is None:
                raise ValueError('Choose a function for Function Explanation, or use Module Summary for a whole file.')
            defaults = {'Security review':'Review concrete security weaknesses with real source evidence; no generic warnings.',
                'Coding-standard / MISRA-oriented review assistance':'Review against applicable original internal engineering rules, explaining relevance and remediation.',
                'Performance observations':'Review concrete static/source-level performance observations with source or analyzer support. No runtime profiling.',
                'Dependency Summary':'Summarize dependencies visible in captured calls and headers; state unresolved relationships.',
                'Control-Flow Summary':'Explain branches and visible control flow; do not claim a complete control-flow graph.'}
            body = {'repository': repository, 'snapshot': status['snapshot'], 'file': file, 'question': question or defaults.get(task, '')}
            if unit:
                body.update(function=unit['symbol'], signature=unit['signature'])
            endpoint = '/review/function' if unit else '/review/file'
            if group == 'Explain':
                endpoint = '/explain/function' if unit else '/explain/module'
            elif group == 'Ask a Question':
                endpoint = '/qa'
            if diagnostics:
                if not origin.strip():
                    raise ValueError('Describe the evidence origin. It is recorded as your declaration, not verified execution history.')
                if mode == 'Choose local file' and value is not None and value.size > 24003:
                    raise ValueError('This file exceeds the maximum size for 6,000 UTF-8 characters. Select a smaller excerpt; nothing was truncated.')
                imported = value.getvalue() if mode == 'Choose local file' and value is not None else value if mode == 'Paste text' else ''
                body.update(text=diagnostic_text(imported), origin=origin.strip(), tool=tool.strip() or 'unknown', tool_version=version.strip() or None,
                            diagnostic_snapshot=status['snapshot'])
                endpoint = '/diagnostics/interpret'
            with st.spinner('Running local analysis. Results must pass citation checks before being displayed…'):
                run = api.request(endpoint, body)
            st.session_state.report = api.request('/analysis-runs/' + run['id'] + '/report?' + urlencode({'repository': repository}))
        except ValueError as exc:
            st.error(str(exc))
        except APIError as exc:
            request_error(exc, write=True)
    if 'report' in st.session_state:
        show_report(api, st.session_state.report, repository, status['snapshot'])


def main():
    if st.session_state.pop('sign_out_requested', False):
        st.session_state.clear()
    if st.session_state.pop('credential_cleanup', False):
        st.session_state.pop('credential', None)
    st.set_page_config(page_title='Secure Code Review', page_icon='🔎', layout='wide')
    st.markdown(STYLE, unsafe_allow_html=True)  # Trusted static CSS only.
    st.title('Secure Code Debugging & Review')
    st.caption('Local/private analysis · Source is not transmitted to an external inference service.')
    token = st.session_state.get('authenticated_token')
    if not token:
        st.subheader('Sign in to your engineering workspace')
        st.caption('Use the local credential supplied by your administrator. It is used only for this session.')
        with st.form('sign-in'):
            credential = st.text_input('Local access credential', type='password', key='credential')
            submit = st.form_submit_button('Sign in', type='primary')
        st.info('After sign-in: choose a repository → index captured source → review or explain → inspect evidence → record your decision.')
        if submit:
            if not credential.strip():
                st.error('Enter your local access credential.')
            else:
                try:
                    API(credential.strip()).request('/repositories')
                    st.session_state.authenticated_token = credential.strip()
                    st.session_state.credential_cleanup = True
                    st.rerun()
                except APIError as exc:
                    request_error(exc)
        return
    try:
        api = API(token)
        with st.sidebar:
            st.subheader('Engineering workspace')
            st.caption('Private local session · source is read-only')
            if st.button('Sign out'):
                st.session_state.sign_out_requested = True
                st.rerun()
        repositories = api.request('/repositories')
        if not repositories:
            st.warning('No repositories are authorized for this identity. Ask your administrator for repository access.')
            return
        repository = st.sidebar.selectbox('Repository', repositories, key='repository')
        if st.session_state.get('report_repository') != repository:
            for key in list(st.session_state):
                if key not in ('authenticated_token', 'repository'):
                    st.session_state.pop(key, None)
            st.session_state.report_repository = repository
        if 'next_navigation' in st.session_state:
            st.session_state.navigation = st.session_state.pop('next_navigation')
        page = st.sidebar.radio('Navigation', PAGES, key='navigation')
        st.caption(repository + ' · ' + page)
        status = api.request('/repositories/' + quote(repository, safe='') + '/status')
        if st.sidebar.button('Index / re-index source', help='Capture and index authorized source. This does not build or modify it.'):
            try:
                with st.spinner('Capturing and indexing authorized source…'):
                    api.request('/repositories/index', {'repository': repository})
                st.session_state.pop('report', None)
                st.session_state.notice = 'Source index updated. Existing reviews retain their original captured version.'
                st.rerun()
            except APIError as exc:
                request_error(exc, write=True)
        if 'notice' in st.session_state:
            st.success(st.session_state.pop('notice'))
        if 'saved_decision' in st.session_state:
            st.success(st.session_state.pop('saved_decision'))
        with st.sidebar.expander('Help and safeguards'):
            st.caption('Indexing captures source evidence. Model and analyzer availability are checked when analysis is requested.')
            st.caption('Findings are candidates, not certified conclusions. Accept/Edit/Reject never changes source.')
            st.caption(STANDARD_NOTICE)
        if status['status'] != 'indexed':
            st.info('This repository has not been indexed. Choose Index / re-index source to capture its C/C++ files.')
            return
        st.sidebar.caption('Indexed source version: ' + status['snapshot'][:12])
        repo_runs = api.request('/repository-reviews?' + urlencode({'repository': repository}))
        running = next((r for r in repo_runs if r['status'] == 'RUNNING'), None)
        if page == 'Overview':
            st.subheader('Your repository at a glance')
            a, b, c = st.columns(3)
            a.metric('Files indexed', len(status['files']))
            b.metric('Functions indexed', status.get('function_count', len(status['functions'])))
            c.metric('Parser failures', sum(s == 'failed' for s in status['parser_status'].values()))
            st.caption('Last indexed: ' + local_time(status.get('indexed_at')) + ' · captured source, not a live filesystem view')
            st.markdown('**Choose your next step**')
            a, b, c = st.columns(3)
            with a:
                if st.button('Review Entire Repository', type='primary', disabled=running is not None):
                    start_repository(api, repository, status['snapshot'])
                st.caption('Find source-backed candidates across every analyzable function.')
            with b:
                if st.button('Explain or review code'):
                    go('Analyze Source')
                st.caption('Understand a selected file or function with citations.')
            with c:
                if st.button('Interpret diagnostics'):
                    go('Diagnostics')
                st.caption('Interpret supplied warnings and logs without executing them.')
            if running:
                st.info('A repository review is already running. Open Repository Review to follow progress.')
            if repo_runs:
                latest = api.request('/repository-reviews/' + repo_runs[0]['id'] + '/report?' + urlencode({'repository': repository}))
                st.subheader('Latest repository review')
                st.caption(OUTCOMES[repo_runs[0]['status']] + ' · ' + local_time(repo_runs[0]['created']))
                if latest['repository_review']['snapshot'] != status['snapshot']:
                    st.warning('The latest review describes a historical source version.')
                summary_cards(latest['summary'])
            else:
                st.info('No repository review yet. Start one above, or explore a selected function first.')
            with st.expander('Source version and indexing details'):
                st.code(status['snapshot'], language='text')
                st.json(status.get('scan', {}))
        elif page == 'Repository Review':
            st.subheader('Review your repository')
            st.caption('One captured source version · one Cppcheck run · sequential function reviews · human decisions')
            if st.button('Review Entire Repository', type='primary', disabled=running is not None):
                start_repository(api, repository, status['snapshot'])
            identifier = running['id'] if running else st.session_state.get('repo_run') or (repo_runs[0]['id'] if repo_runs else None)
            if identifier:
                repository_dashboard(api, repository, identifier, status['snapshot'])
            else:
                st.info('Start a review to see progress, coverage and candidate findings.')
        elif page in ('Analyze Source', 'Diagnostics'):
            st.subheader('Understand and review code' if page == 'Analyze Source' else 'Interpret diagnostics')
            analyze_source(api, repository, status, diagnostics=page == 'Diagnostics')
        elif page == 'Findings':
            st.subheader('Findings awaiting your assessment')
            st.caption('Latest 100 candidates in your authorized scope. Evidence is loaded for the selected finding only.')
            rows = api.request('/findings?' + urlencode({'repository': repository, 'include_review_state': 'true'}))
            findings_table(api, rows, repository, 'all-findings', status['snapshot'])
        else:
            st.subheader('History & Reports')
            st.caption('Latest 100 repository reviews and analysis runs in this authorized scope. Times are displayed in IST; exports retain original provenance.')
            if repo_runs:
                options = {r['id']: f'Review {i + 1} · ' + local_time(r['created']) + ' · ' + OUTCOMES[r['status']] for i, r in enumerate(repo_runs)}
                rid = st.selectbox('Repository review', list(options), format_func=options.get)
                document = api.request('/repository-reviews/' + rid + '/report?' + urlencode({'repository': repository}))
                summary_cards(document['summary'])
                downloads(document, 'history-repository-' + rid)
                if st.button('Inspect this repository review'):
                    st.session_state.repo_run = rid
                    go('Repository Review')
            runs = api.request('/analysis-runs?' + urlencode({'repository': repository}))
            if runs:
                labels = {r['id']: f'Run {i + 1} · ' + local_time(r['created']) + ' · ' + r['mode'].replace('_', ' ') + ' · ' + OUTCOMES.get(r['outcome'], r['outcome']) for i, r in enumerate(runs)}
                rid = st.selectbox('Individual analysis', list(labels), format_func=labels.get)
                if st.button('Open analysis report'):
                    st.session_state.report = api.request('/analysis-runs/' + rid + '/report?' + urlencode({'repository': repository}))
                if 'report' in st.session_state:
                    show_report(api, st.session_state.report, repository, status['snapshot'])
            elif not repo_runs:
                st.info('No history yet. A completed analysis and your decisions will appear here.')
    except APIError as exc:
        request_error(exc)


if __name__ == '__main__':
    main()

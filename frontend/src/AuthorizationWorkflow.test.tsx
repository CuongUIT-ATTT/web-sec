import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { AuthorizationWorkflow, selectionBudget } from './AuthorizationWorkflow';
import { api, type AuthorizationCase } from './api';
vi.mock('./api', () => ({api: {authorizationConfig: vi.fn(), authorizationPreview: vi.fn(), runs: vi.fn(), queueAuthorization: vi.fn(), authorizationResults: vi.fn(), cancelRun: vi.fn()}}));
afterEach(cleanup);
const row: AuthorizationCase = {case_id:'stable-1',kind:'BOLA',operation_id:1,method:'GET',path_template:'/books/{id}',actor_identity_id:1,actor_role:'user',resource_id:1,owner_identity_id:2,relationship:'CROSS_IDENTITY',expected_decision:'DENY',matched_rule_keys:['deny'],policy_revision:'r1',baseline_identity_id:2,execution_eligible:true,reasons:[]};
it('deduplicates shared baselines and verifies every selected actor and baseline', () => {
 expect(selectionBudget([row,{...row,case_id:'stable-2',actor_identity_id:3}])).toBe(6);
});
it('shows exclusions, requires explicit GET selection and uses new queue contract', async () => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{rules:[],operations:[],sharing:[]}});
 vi.mocked(api.runs).mockResolvedValue([]);
 const preview = {policy_revision:'r1',cases:[row,{...row,case_id:'write',method:'POST',execution_eligible:false,reasons:['DISPOSABLE_WRITE_AUTHORIZATION_REQUIRED']}],exclusions:[{identity_id:4,reason:'MISSING_CREDENTIAL'}],warnings:[],identity_count:4,actor_case_count:2,executable_case_count:1,planned_attempts:4,request_limit:10};
 vi.mocked(api.authorizationPreview).mockResolvedValue(preview);
 vi.mocked(api.queueAuthorization).mockResolvedValue({id:8});
 render(<AuthorizationWorkflow projectId={1} targets={[{id:2,project_id:1,base_url:'http://127.0.0.1:5000',timeout_seconds:2,request_limit:10,verification_path:'/me'}]} setup={<p>Setup fixture</p>} legacy={<p>History</p>} />);
 fireEvent.click(screen.getByRole('button',{name:'Matrix'}));
 fireEvent.change(screen.getByLabelText('API đích cho ma trận'),{target:{value:'2'}});
 fireEvent.click(screen.getByText('Tạo lại preview'));
 await screen.findByText('Identity #4: MISSING_CREDENTIAL');
 expect(screen.getByLabelText('Chọn write')).toBeDisabled();
 expect(screen.getByText('Xem lựa chọn trước khi chạy')).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Chọn stable-1'));
 fireEvent.click(screen.getByText('Xem lựa chọn trước khi chạy'));
 fireEvent.click(screen.getByText('Queue các case GET đã chọn'));
 await screen.findByText('Đã queue Run #8');
 expect(api.queueAuthorization).toHaveBeenCalledWith(1,2,'r1',['stable-1']);
});
it('rejects a changed preview before queueing and clears the selection', async () => {
 vi.mocked(api.queueAuthorization).mockClear();
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([]);
 const preview = {policy_revision:'r1',cases:[row],exclusions:[],warnings:[],identity_count:1,actor_case_count:1,executable_case_count:1,planned_attempts:4,request_limit:10};
 vi.mocked(api.authorizationPreview).mockResolvedValueOnce(preview).mockResolvedValue({...preview,policy_revision:'r2'});
 render(<AuthorizationWorkflow projectId={1} targets={[{id:2,project_id:1,base_url:'http://127.0.0.1:5000',timeout_seconds:2,request_limit:10,verification_path:'/me'}]} setup={<p>Fixture</p>} legacy={<p>History</p>}/>);
 fireEvent.click(screen.getByRole('button',{name:'Matrix'}));
 fireEvent.change(screen.getByLabelText('API đích cho ma trận'),{target:{value:'2'}});
 fireEvent.click(screen.getByText('Tạo lại preview'));
 await screen.findByLabelText('Chọn stable-1');
 fireEvent.click(screen.getByLabelText('Chọn stable-1'));
 fireEvent.click(screen.getByText('Xem lựa chọn trước khi chạy'));
 fireEvent.click(screen.getByText('Queue các case GET đã chọn'));
 await screen.findByText(/STALE_PREVIEW/);
 expect(api.queueAuthorization).not.toHaveBeenCalled();
 expect(screen.getByText('Queue các case GET đã chọn')).toBeDisabled();
});
it('renders durable case findings and leaves manual/ZAP unexecuted', async () => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([{id:5,project_id:1,status:'COMPLETED',snapshot:{run_kind:'AUTOAUTH_SELECTED'},execution_summary:null}]);
 vi.mocked(api.authorizationResults).mockResolvedValue({run_id:5,status:'COMPLETED',policy_revision:'r1',cases:[{case_id:'stable-1',run_id:5,result_id:7,finding_id:'autoauth-result:7',artifact_ref:'run:5:result:7',policy_revision:'r1',matched_rule_keys:['deny'],kind:'BFLA',expected_decision:'DENY',actor_identity_id:1,resource_id:null,baseline_identity_id:3,execution_status:'COMPLETED_RESPONSE',conclusion:'CONFIRMED_VIOLATION',reason_codes:['disclosure'],http_status:403,evidence:{baseline_valid:true}}]});
 render(<AuthorizationWorkflow projectId={1} targets={[]} setup={null} legacy={null}/>);
 fireEvent.click(screen.getByRole('button',{name:'Results'}));
 await screen.findByRole('option',{name:'Run #5 · COMPLETED'});
 fireEvent.change(screen.getByLabelText('Run tự động'),{target:{value:'5'}});
 await screen.findByText('autoauth-result:7');
 expect(screen.getByText('run:5:result:7')).toBeTruthy();
 // Native terms associate labels and values without relying on the visual header.
 const fields = document.querySelector('.result-fields')!;
 expect(fields.tagName).toBe('DL');
 const pairs = [...fields.children].map(group => [group.querySelector('dt')!, group.querySelector('dd')!]);
 expect(pairs.map(([term]) => term.textContent)).toEqual(['Người gọi','Tài nguyên / chức năng','Policy dự kiến','HTTP quan sát','Kết luận']);
 expect(pairs.map(([,value]) => value.textContent)).toEqual([
   expect.stringContaining('Danh tính #1'), expect.stringContaining('Chức năng'), 'DENY',
   expect.stringContaining('403'), expect.stringContaining('CONFIRMED_VIOLATION'),
 ]);
 for (const [term,value] of pairs) {
   expect(term.closest('[aria-hidden="true"]')).toBeNull();
   expect(value.closest('[aria-hidden="true"]')).toBeNull();
 }

 fireEvent.click(screen.getByRole('button',{name:'Comparison'}));
 await screen.findByText(/Manual và OWASP ZAP: NOT_RUN/);
 expect(screen.getAllByText('NOT_RUN / UNAVAILABLE')).toHaveLength(2);
});

it('shows progress counters and cancels the selected running job once', async () => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([{id:6,project_id:1,status:'RUNNING',snapshot:{run_kind:'AUTOAUTH_SELECTED',policy_revision:'r1'},execution_summary:{planned_attempts:8,transport_attempts:2,completed_responses:1,scope_blocked:0,transport_errors:1,cancelled_cases:0}}]);
 let finish!: () => void;
 vi.mocked(api.cancelRun).mockReturnValue(new Promise<void>(resolve=>{finish=resolve;}));
 render(<AuthorizationWorkflow projectId={1} targets={[]} setup={null} legacy={null}/>);
 fireEvent.click(screen.getByRole('button',{name:'Run'}));
 const cancel=await screen.findByRole('button',{name:'Hủy Run #6'});
 await screen.findByText(/Planned 8 · transport 2 · responses 1/);
 fireEvent.click(cancel); fireEvent.click(cancel);
 expect(api.cancelRun).toHaveBeenCalledTimes(1);
 expect(api.cancelRun).toHaveBeenCalledWith(6);
 finish();
});

it.each([
 ['NOT_RUN','CANCELLED'],
 ['NOT_RUN','REQUEST_LIMIT_REACHED'],
 ['INSUFFICIENT_EVIDENCE','BODY_TRUNCATED'],
])('filters %s results while preserving execution status %s', async (conclusion, status) => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([{id:5,project_id:1,status:'CANCELLED',snapshot:{run_kind:'AUTOAUTH_SELECTED'},execution_summary:null}]);
 vi.mocked(api.authorizationResults).mockResolvedValue({run_id:5,status:'CANCELLED',policy_revision:'r1',cases:[{case_id:'closure-case',run_id:5,result_id:7,finding_id:null,artifact_ref:'run:5:result:7',policy_revision:'r1',matched_rule_keys:[],kind:'BOLA',expected_decision:'DENY',actor_identity_id:1,resource_id:1,baseline_identity_id:2,execution_status:status,conclusion,reason_codes:['execution.preserved'],http_status:null,evidence:{}}]});
 render(<AuthorizationWorkflow projectId={1} targets={[]} setup={null} legacy={null}/>);
 fireEvent.click(screen.getByRole('button',{name:'Results'}));
 await screen.findByRole('option',{name:'Run #5 · CANCELLED'});
 fireEvent.change(screen.getByLabelText('Run tự động'),{target:{value:'5'}});
 await screen.findByText('closure-case');
 fireEvent.change(screen.getByLabelText('Lọc kết luận'),{target:{value:conclusion}});
 expect(screen.getByText('closure-case')).toBeTruthy();
 expect(screen.getByText(status+' · HTTP —')).toBeTruthy();
 expect(screen.getByText(/execution\.preserved/)).toBeTruthy();
 fireEvent.change(screen.getByLabelText('Lọc kết luận'),{target:{value:'CONFIRMED_VIOLATION'}});
 expect(screen.queryByText('closure-case')).toBeNull();
});

it('never resolves legacy historical identity labels from current configuration', async () => {
 const {historicalIdentity}=await import('./AuthorizationWorkflow');
 expect(historicalIdentity(undefined,4)).toContain('thiếu nhãn snapshot');
 expect(historicalIdentity({id:4,display_name:'userB-at-queue',role:'user',source:'SNAPSHOT'},4)).toBe('userB-at-queue (user) · #4');
});

it('shows actor and owner names for same-role identities without narrowing matrix coverage', async () => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([]);
 vi.mocked(api.authorizationPreview).mockResolvedValue({policy_revision:'r1',cases:[row,{...row,case_id:'second',actor_identity_id:2,owner_identity_id:1}],exclusions:[],warnings:[],identity_count:2,actor_case_count:2,executable_case_count:2,planned_attempts:6,request_limit:10});
 render(<AuthorizationWorkflow projectId={1} targets={[{id:2,project_id:1,base_url:'http://127.0.0.1:5000',timeout_seconds:2,request_limit:10,verification_path:'/me'}]} identities={[1,2].map(id=>({id,display_name:id===1?'userA':'userB',role:'user',principal_pointer:null,expected_principal:null,has_secret:true}))} setup={null} legacy={null}/>);
 fireEvent.click(screen.getByRole('button',{name:'Matrix'}));
 fireEvent.change(screen.getByLabelText('API đích cho ma trận'),{target:{value:'2'}});
 fireEvent.click(screen.getByText('Tạo lại preview'));
 await screen.findByLabelText('Chọn second');
 expect(screen.getAllByText('userA (user) · #1').length).toBeGreaterThan(0);
 expect(screen.getAllByText('userB (user) · #2').length).toBeGreaterThan(0);
 expect(screen.getAllByRole('checkbox')).toHaveLength(2);
 fireEvent.change(screen.getByLabelText('Identity'),{target:{value:'2'}});
 expect(screen.getAllByRole('checkbox')).toHaveLength(1);
 expect(screen.getByLabelText('Chọn second')).toBeTruthy();
});

it('paginates a large result set without dropping cases and preserves historical snapshot names', async () => {
 vi.mocked(api.authorizationConfig).mockResolvedValue({revision:'r1',configuration:{}});
 vi.mocked(api.runs).mockResolvedValue([{id:5,project_id:1,status:'CANCELLED',snapshot:{run_kind:'AUTOAUTH_SELECTED'},execution_summary:null}]);
 const label={id:1,display_name:'actor-at-queue',role:'user',source:'SNAPSHOT'};
 const cases=Array.from({length:123},(_,i)=>({case_id:`large-${i}`,run_id:5,result_id:i,finding_id:null,artifact_ref:null,policy_revision:'r1',matched_rule_keys:[],kind:'BOLA',expected_decision:'DENY',actor_identity_id:1,resource_id:1,baseline_identity_id:2,execution_status:'CANCELLED',conclusion:'NOT_RUN',reason_codes:['execution.cancelled'],http_status:null,evidence:null,presentation:{actor:label,owner:{...label,id:2,display_name:'owner-at-queue'},planned_baseline:{...label,id:2},actual_baseline:{...label,id:null,display_name:null},resource_name:'book-at-queue',method:'GET',path:'/books/{id}',relationship:'CROSS_IDENTITY',baseline_kind:'OWNER',baseline_provenance:'NOT_OBSERVED'}}));
 vi.mocked(api.authorizationResults).mockResolvedValue({run_id:5,status:'CANCELLED',policy_revision:'r1',cases});
 render(<AuthorizationWorkflow projectId={1} targets={[]} setup={null} legacy={null} identities={[{id:1,display_name:'RENAMED-NOW',role:'admin',principal_pointer:null,expected_principal:null,has_secret:false}]}/>);
 fireEvent.click(screen.getByRole('button',{name:'Results'}));
 await screen.findByRole('option',{name:'Run #5 · CANCELLED'});
 fireEvent.change(screen.getByLabelText('Run tự động'),{target:{value:'5'}});
 await screen.findByText('123 kết quả · Trang 1/3');
 expect(document.querySelectorAll('.result-item')).toHaveLength(50);
 expect(screen.queryByText(/RENAMED-NOW/)).toBeNull();
 fireEvent.click(screen.getByText('Trang kết quả sau'));fireEvent.click(screen.getByText('Trang kết quả sau'));
 expect(document.querySelectorAll('.result-item')).toHaveLength(23);
 expect(screen.getByText('123 kết quả · Trang 3/3')).toBeTruthy();
 expect(screen.getAllByText('actor-at-queue (user) · #1')).toHaveLength(23);
});

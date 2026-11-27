import { afterEach, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { AuthorizationConfigEditor } from './AuthorizationConfigEditor';
afterEach(cleanup);
it('builds reusable owner rules, explicit mappings and sharing without per-case policies', () => {
 function Harness() {const [value,setValue]=useState('{"rules":[],"operations":[],"sharing":[]}');return <><AuthorizationConfigEditor value={value} onChange={setValue} operations={[{id:7,method:'GET',path:'/books/{id}',selected:true,operation_key:'read'}]} types={[{id:3,name:'book',resource_id_pointer:'/id',restricted_pointers:['/secret']}]} resources={[{id:9,resource_type_id:3,external_id:'redacted',owner_identity_id:1,path_parameter:'id'}]} identities={[{id:2,display_name:'Reader',role:'user',principal_pointer:null,expected_principal:null,has_secret:true}]}/><output data-testid="config">{value}</output></>;}
 render(<Harness/>);
 fireEvent.change(screen.getByLabelText('Operation cần phê duyệt'),{target:{value:'7'}});
 fireEvent.change(screen.getByLabelText('Resource type mapping'),{target:{value:'3'}});
 fireEvent.click(screen.getByText('Xác nhận mapping và phê duyệt'));
 fireEvent.change(screen.getByLabelText('Tên quy tắc'),{target:{value:'owner'}});
 fireEvent.change(screen.getByLabelText('Quan hệ áp dụng'),{target:{value:'OWNER'}});
 fireEvent.click(screen.getByText('Thêm quy tắc'));
 fireEvent.change(screen.getByLabelText('Tài nguyên chia sẻ'),{target:{value:'9'}});
 fireEvent.change(screen.getByLabelText('Danh tính được chia sẻ'),{target:{value:'2'}});
 fireEvent.click(screen.getByText('Thêm chia sẻ'));
 const config=JSON.parse(screen.getByTestId('config').textContent!);
 expect(config.operations).toEqual([{operation_id:7,kind:'BOLA',approved:true,resource_type_id:3}]);
 expect(config.rules[0]).toMatchObject({key:'owner',relation:'OWNER',decision:'ALLOW',operation_ids:[7]});
 expect(config.sharing).toEqual([{resource_id:9,identity_ids:[2]}]);
});

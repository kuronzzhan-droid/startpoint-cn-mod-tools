"""Read-only plans and bounded atomic writes shared by offline receiver helpers."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def sha(raw): return None if raw is None else hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result: raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    def invalid(value): raise ValueError('invalid JSON number '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def checked_path(root, relative):
    root=Path(root).absolute(); path=root/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('unsafe relative path')
    for item in [path,*path.parents]:
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise ValueError('symlink/junction path requires review: '+str(item))
        if item==root: break
    if not path.resolve().is_relative_to(root.resolve()): raise ValueError('path escapes root')
    return path


def entry(path,before,after,**fields):
    return dict(path=path,before=before,after=after,**fields)


def describe(plan):
    return {k:str(v)if isinstance(v,Path)else v for k,v in plan.items()if k not in ('before','after')} | {
        'before_sha256':sha(plan['before']),'after_sha256':sha(plan['after']),
        'after_bytes':len(plan['after']),'changed':plan['before']!=plan['after']}


def cas(plans):
    for item in plans:
        path=item['path']
        if not path.is_absolute() or path.resolve()!=path:
            raise ValueError('preflight path alias: '+str(path))
        raw=path.read_bytes()if path.exists()else None
        if raw!=item['before']: raise ValueError('preflight drift: '+str(path))


def atomic_write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.wf-update-'+uuid.uuid4().hex+'.partial')
    with temporary.open('xb')as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    for attempt in range(6):
        try: temporary.replace(path); return
        except PermissionError:
            if attempt==5: raise
            time.sleep(0.2*(attempt+1))


def apply_plans(plans,backup_root):
    """Caller must run every resource/client/server plan first; no publishing here."""
    cas(plans); backup_root=Path(backup_root)
    if backup_root.exists(): raise ValueError('backup root already exists')
    backup_root.mkdir(parents=True)
    def record(name,value):
        atomic_write(backup_root/name,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    receipts=[describe(p)|{'index':i,'before_file':None if p['before']is None else str(i)+'.before'}
              for i,p in enumerate(plans)]
    record('receipt.json',receipts)
    state=dict(complete=False,backups_complete=False,backed_up=[],applied=[],attempted=None,published=False)
    record('transaction.json',state)
    try:
        for i,item in enumerate(plans):
            if item['before']is not None:
                path=backup_root/(str(i)+'.before')
                with path.open('xb')as stream:
                    stream.write(item['before']);stream.flush();os.fsync(stream.fileno())
                if path.read_bytes()!=item['before']:raise ValueError('table backup readback mismatch')
                state['backed_up'].append(i)
        state['backups_complete']=True;record('transaction.json',state)
        cas(plans)
        for i,item in enumerate(plans):
            if item['before']!=item['after']:
                state['attempted']=i;record('transaction.json',state)
                cas([item]);atomic_write(item['path'],item['after'])
                if item['path'].read_bytes()!=item['after']:raise ValueError('table write readback mismatch')
                state['applied'].append(i);state['attempted']=None
                record('transaction.json',state)
        for item in plans:
            if item['path'].resolve()!=item['path']or item['path'].read_bytes()!=item['after']:
                raise ValueError('table final readback mismatch')
        state['complete']=True
    except BaseException as exc:
        state['error']=type(exc).__name__+': '+str(exc)
        state['recovery']='Compare receipt hashes and attempted/applied indices; keep all preimages. Do not retry or restore blindly.'
        raise
    finally:record('transaction.json',state)

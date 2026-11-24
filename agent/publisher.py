import os
from datetime import datetime,timedelta
import requests
from requests_oauthlib import OAuth1


class Rejected(Exception):
    """X explicitly rejected this request. A later attempt is safe."""


class Publisher:
    def __init__(self,account):
        self.account=str(account)
        self.session=requests.Session()
        self.session.auth=OAuth1(os.environ['X_API_KEY'],os.environ['X_API_SECRET'],
                                 os.environ['X_ACCESS_TOKEN'],os.environ['X_ACCESS_TOKEN_SECRET'])
        self.base='https://api.x.com/2/'

    def read(self,path,params=None):
        response=self.session.get(self.base+path,params=params,timeout=(5,15),allow_redirects=False)
        response.raise_for_status()
        return response.json()

    def verify(self):
        if self.read('users/me')['data']['id']!=self.account:
            raise ValueError('account_identity_mismatch')

    def send(self,text,media_id=None):
        payload={'text':text}
        if media_id:
            payload['media']={'media_ids':[str(media_id)]}
        r=self.session.post(self.base+'tweets',json=payload,timeout=(5,15),allow_redirects=False)
        if r.status_code in (400,401,402,403,422,429):
            raise Rejected(f'x_rejected_{r.status_code}')
        r.raise_for_status()
        ident=r.json()['data']['id']
        if not str(ident).isdigit():
            raise ValueError('unrecognised_receipt')
        return str(ident)

    def reconcile(self,slot):
        start=datetime.fromisoformat(slot['intent_at'])-timedelta(seconds=10)
        params={'start_time':start.isoformat(timespec='seconds'),'tweet.fields':'created_at',
                'exclude':'retweets,replies','max_results':100}
        for _ in range(3):
            page=self.read(f'users/{self.account}/tweets',params)
            for post in page.get('data',[]):
                if post.get('text')==slot['draft']['text']:
                    return post['id']
            token=page.get('meta',{}).get('next_token')
            if not token:
                break
            params['pagination_token']=token
        return None

    def attach(self,draft):
        """An optional licensed illustration. No media upload for shadow runs."""
        import images
        if os.getenv('AGENT_COMMONS_IMAGES','').lower()!='true' or draft.get('kind')!='evergreen':
            return None
        try:
            found=images.find_commons_image(draft['topic'],draft['text'],set())
            if found:
                return images.upload_to_x(found['bytes'],found['description'] or found['title'])
        except Exception:
            return None

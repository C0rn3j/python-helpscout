# Help Scout API client

This package contains a wrapper to query Help Scout's API.
The package tries to be as general and assume as little as possible about the
API. Therefore, it will allow any endpoint to be requested and objects and
types will be created on the fly.

Information about the available endpoints, objects and other stuff can be found
on the [API's documentation](https://developer.helpscout.com/mailbox-api/).
The client contains as little internal knowledge of the API as possible, mostly
authentication, pagination and how are objects returned.

In order to handle pagination calls to API are done inside a generator.
As a consequence, even post and deletes have to be "nexted" if using the *hit_*
method.

## Requirements

Python 3.11+

## Installation

Using PyPI into a [venv](https://docs.python.org/3/library/venv.html):
```bash
pip install python-helpscout --require-virtualenv`
```

Manually by cloning the repository and executing pip into a [venv](https://docs.python.org/3/library/venv.html):
```bash
pip install . --require-virtualenv`
```


## Authentication

In order to use the API you need an app id and app secret.

More about credentials can be found in
[Help Scout's documentation](https://developer.helpscout.com/mailbox-api/overview/authentication/).

## General use

The general use is by instantiating a client and then hitting the API by
doing `client.<endpoint>.<method>(<resource_id>, <params>)`. Where:

* *Endpoint* is one of the endpoints defined in the API's documentation.
* *Method* is one of get, post, patch, put or delete as defined in the API.
* *Resource id* can be None or the id of the specific resource to access,
  update or delete. E.g.: a conversation id.
* *Params* can be None, a string or a dictionary with the parameters to access
  in the get method or the data to send otherwise.

To access attributes of specific resources, like the tags of a conversation,
you can do:
`client.<endpoint>[<resource_id>].<attribute>.<method>(<resource_id>, <params>)`.

Example: `client.conversations[212109].threads.get()`

## Examples

### Listing all users

```python
> from helpscout import HelpScout
> hs = HelpScout(app_id='ax0912n', app_secret='axon129')
> users = hs.users.get()
> users[0]
User(id=12391,
     firstName="John",
     lastName="Doe",
     email="john.doe@gmail.com",
     role="user",
     timezone="America/New_York",
     createdAt="2019-01-03T19:00:00Z",
     updatedAt="2019-05-20T18:00:00Z",
     type="user",
     mention="johnny",
     initials="JD",
     _links={'self': {'href': 'https://api.helpscout.net/v2/users/12391'}})
> users[1].id
9320
```

### Hitting the API directly to get all mailboxes

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='laknsdo', app_secret='12haosd9')
> for mailbox in hs.hit('mailboxes', 'get'):
>      print(mailbox)
{'mailboxes': [
   {'id': 1930,
    'name': 'Fake Support',
    'slug': '0912301u',
    'email': 'support@fake.com',
    'createdAt': '2018-12-20T20:00:00Z',
    'updatedAt': '2019-05-01T16:00:00Z',
    '_links': {
      'fields': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/fields/'},
      'folders': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/folders/'},
      'self': {'href': 'https://api.helpscout.net/v2/mailboxes/1930'}
    }
   }
 ]
}
```

### Hitting the API directly to get all mailboxes but handling requests with pagination as iteration goes on

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='laknsdo', app_secret='12haosd9')
> for mailbox in hs.hit_('mailboxes', 'get'):
>      print(mailbox)
{'mailboxes': [
   {'id': 1930,
    'name': 'Fake Support',
    'slug': '0912301u',
    'email': 'support@fake.com',
    'createdAt': '2018-12-20T20:00:00Z',
    'updatedAt': '2019-05-01T16:00:00Z',
    '_links': {
      'fields': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/fields/'},
      'folders': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/folders/'},
      'self': {'href': 'https://api.helpscout.net/v2/mailboxes/1930'}
    }
   }
 ]
}
```

### Hitting the API directly to get a specific mailbox

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='laknsdo', app_secret='12haosd9')
> for mailbox in hs.hit('mailboxes', 'get', resource_id=1930):
>      print(mailbox)
{'id': 1930,
 'name': 'Fake Support',
 'slug': '0912301u',
 'email': 'support@fake.com',
 'createdAt': '2018-12-20T20:00:00Z',
 'updatedAt': '2019-05-01T16:00:00Z',
 '_links': {
   'fields': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/fields/'},
   'folders': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/folders/'},
   'self': {'href': 'https://api.helpscout.net/v2/mailboxes/1930'}
 }
}
```

### Hitting the API directly to get a specific mailbox dictionary style

In this case, you will have to select the first element of the list yourself,
as it is not quite clear if one or more elements should be expected from the
api depending on the endpoint.

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='laknsdo', app_secret='12haosd9')
> print(hs.mailboxes[1930].get())
Mailbox(
 id=1930,
 name='Fake Support',
 slug='0912301u',
 email='support@fake.com',
 createdAt='2018-12-20T20:00:00Z',
 updatedAt='2019-05-01T16:00:00Z',
 _links={
   'fields': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/fields/'},
   'folders': {'href': 'https://api.helpscout.net/v2/mailboxes/1930/folders/'},
   'self': {'href': 'https://api.helpscout.net/v2/mailboxes/1930'}
 }
)
```

### Listing conversations using a dictionary parameters

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='asd12', app_secret='onas912')
> params = {'status': 'active'}
> conversations = hs.conversations.get(params=params)
```

### Listing conversations using a string with parameters

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='asdon123', app_secret='asdoin1')
> params = 'query=(createdAt:[2019-06-20T00:00:00Z TO 2019-06-22T23:59:59Z])'
> conversations = hs.conversations.get(params=params)
```

### Deleting a conversation

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='asdon123', app_secret='asdoin1')
> conversation_id = 10
> hs.conversations.delete(resource_id=conversation_id)
```

### Requesting a pre-made report

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='asdon123', app_secret='asdoin1')
> report_url = 'reports/happiness?start=2019-06-01T00:00:00Z&end=2019-06-15:00:00Z'
> next(hs.hit_(report_url, 'get'))
...
```

or

```python
> from helpscout.client import HelpScout
> hs = HelpScout(app_id='asdon123', app_secret='asdoin1')
> report_url = 'reports/happiness?start=2019-06-01T00:00:00Z&end=2019-06-15:00:00Z'
> hs.hit(report_url, 'get')
...
```

### Adding tags to a conversation

```python
> from helpscout import HelpScout
> helpscout_client = HelpScout(app_id='ax0912n', app_secret='axon129')
> conversation_id = 999
> endpoint = 'conversations/%s/tags' % conversation_id
> data = {'tags': conversation_tags}
> helpscout_client.hit(endpoint, 'put', data=data)
```

or

```python
> from helpscout import HelpScout
> helpscout_client = HelpScout(app_id='ax0912n', app_secret='axon129')
> conversation_id = 999
> endpoint = 'conversations/%s/tags' % conversation_id
> data = {'tags': conversation_tags}
> next(helpscout_client.hit_(endpoint, 'put', data=data))
```

or

```python
> from helpscout import HelpScout
> helpscout_client = HelpScout(app_id='ax0912n', app_secret='axon129')
> conversation_id = 999
> data = {'tags': conversation_tags}
> helpscout_client.conversations[999].tags.put(data=data)
```

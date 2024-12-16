from __future__ import annotations

import logging
import time
import typing
from typing import overload

import requests

if typing.TYPE_CHECKING:
	from collections.abc import Callable, Generator
	from typing import Literal

from functools import partial
from urllib.parse import urljoin

from helpscout.exceptions import (
	HelpScoutAuthenticationException,
	HelpScoutException,
	HelpScoutRateLimitExceededException,
)
from helpscout.model import HelpScoutObject

logger = logging.getLogger('HelpScout')
EmbeddedKey = '_embedded'
PageKey = 'page'


class HelpScout:

	def __init__(
		self, app_id: str, app_secret: str,
		base_url: str = 'https://api.helpscout.net/v2/',
		sleep_on_rate_limit_exceeded: bool = True,
		rate_limit_sleep: int = 10
	) -> None:
		"""Help Scout API v2 client wrapper.

		The app credentials are created on the My App section in your profile.
		More about credentials here:
		https://developer.helpscout.com/mailbox-api/overview/authentication/

		Parameters
		----------
		app_id: str
			The application id.
		app_secret: str
			The application secret.
		base_url: str
			The API's base url.
		sleep_on_rate_limit_exceeded: bool
			True to sleep and retry on rate limits exceeded.
			Otherwise raises an HelpScoutRateLimitExceededException exception.
		rate_limit_sleep: int
			Amount of seconds to sleep when the rate limit is exceeded if
			sleep_on_rate_limit_exceeded is True.

		"""
		self.app_id = app_id
		self.app_secret = app_secret
		self.base_url = base_url
		self.sleep_on_rate_limit_exceeded = sleep_on_rate_limit_exceeded
		self.rate_limit_sleep = rate_limit_sleep
		self.access_token = None

	def __getattr__(self, endpoint: str) -> HelpScoutEndpointRequester:
		"""Returns a request to hit the API in a nicer way

		E.g.:
		> client = HelpScout(app_id='asdasd', app_secret='1021')
		> client.conversations.get()
		...
		> client.conversations.delete('/3')


		Parameters
		----------
		endpoint: str
			One of the endpoints in the API. E.g.: conversations, mailboxes.

		Returns
		-------
		HelpScoutEndpointRequester
			An object that through the get/post/put/patch/delete callable
			attributes forwards the requests to the appropriate get_objects /
			hit client calls.

		"""
		return HelpScoutEndpointRequester(self, endpoint, False)

	def get_objects(self, endpoint:str, resource_id:int|str|None=None, params:dict|str|None=None, specific_resource:bool=False) -> HelpScoutObject|list[HelpScoutObject]:
		"""Returns the objects from the endpoint filtering by the parameters.

		Parameters
		----------
		endpoint: str
			One of the endpoints in the API. E.g.: conversations, mailboxes.
		resource_id: int | str | None
			The id of the resource in the endpoint to query.
			E.g.: in "GET /v2/conversations/123 HTTP/1.1" the id would be 123.
			If None is provided, nothing will be done
		params: dict | str | None
			Dictionary with the parameters to send to the url.
			Or the parameters already un url format.
		specific_resource: bool
			Specifies if the endpoint is for an specific resource_id even if
			the id is contained in the endpoint uri and resource_id None is
			provided.

		Returns
		-------
		HelpScoutObject | list[HelpScoutObject]
			A list of objects returned by the api.

		"""
		cls = HelpScoutObject.cls(endpoint, endpoint)
		results:list[HelpScoutObject] = cls.from_results( self.hit_(endpoint, 'get', resource_id, params=params) )
		if resource_id is not None or specific_resource:
			return results[0]
		return results

	def hit(self, endpoint:str, method:str, resource_id:int|str|None=None, data:dict|None=None, params:dict|str|None=None) -> list[dict|None]:
		"""Hits the api and returns all the data.

		If several calls are needed due to pagination, control won't be
		returned to the caller until all is retrieved.

		Parameters
		----------
		endpoint: str
			The API endpoint.
		method: str
			The http method to hit the endpoint with.
			One of {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
		resource_id: int | str | None
			The id of the resource in the endpoint to query.
			E.g.: in "GET /v2/conversations/123 HTTP/1.1" the id would be 123.
			If None is provided, nothing will be done
		dict: dict | None
			A dictionary with the data to send to the API as json.
		params: dict | str | None
			Dictionary with the parameters to send to the url.
			Or the parameters already un url format.

		Returns
		-------
		list[dict] | list[None]
			list: when several objects are received from the API, a list of
				dictionaries with HelpScout's _embedded data will be returned
			None if http 201 created or 204 no content are received.

		"""
		return list(self.hit_(endpoint, method, resource_id, data, params))

	def hit_(
		self, endpoint:str, method:str,
		resource_id: int | str | None = None,
		data: dict | None = None,
		params: dict | str | None = None,
	) -> Generator[dict | None, None, None]:
		"""Hits the api and yields the data.

		Parameters
		----------
		endpoint: str
			The API endpoint.
		method: str
			The http method to hit the endpoint with.
			One of {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
		resource_id: int | str | None
			The id of the resource in the endpoint to query.
			E.g.: in "GET /v2/conversations/123 HTTP/1.1" the id would be 123.
			If None is provided, nothing will be done
		data: dict | None
			A dictionary with the data to send to the API as json.
		params: dict | str | None
			Dictionary with the parameters to send to the url.
			Or the parameters already un url format.

		Yields
		------
		dict | None
			Dictionary with HelpScout's _embedded data.
			None if http 201 created or 204 no content are received.

		"""
		if self.access_token is None:
			self._authenticate()
		url = urljoin(self.base_url, endpoint)
		if resource_id is not None:
			url = urljoin(url + '/', str(resource_id))
		if params:
			if isinstance(params, dict):
				params = '&'.join(f'{k}={v}' for k, v in params.items())
			url = f'{url}?{params}'
		headers = self._authentication_headers()
		logger.debug(f'Request: {method} {url}')
		r = getattr(requests, method)(url, headers=headers, json=data)
		ok, status_code = r.ok, r.status_code
		logger.debug(f'Received: {method} {url} ({ok} - {status_code})')
		if status_code in (201, 204):
			yield
		elif ok:
			response = r.json()
			for item in self._results_with_pagination(response, method):
				yield item
		elif status_code == 401:
			self._authenticate()
			for item in self.hit_(endpoint, method, resource_id, data):
				yield item
		elif status_code == 429:
			self._handle_rate_limit_exceeded()
			for item in self.hit_(endpoint, method, resource_id, data):
				yield item
		else:
			raise HelpScoutException(r.text)

	def _results_with_pagination(self, response:dict, method:str) -> Generator[dict, None, None]:
		"""Requests and yields pagination results.

		Parameters
		----------
		response: dict
			A dictionary with a previous api response return value
		method: str
			The http method to hit the endpoint with.
			One of {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}

		Yields
		------
		dict
			The dictionary response from help scout.

		"""
		if EmbeddedKey not in response or PageKey not in response:
			yield response
			return
		if isinstance(response[EmbeddedKey], list):
			for item in response[EmbeddedKey]:
				yield item
		else:
			yield response[EmbeddedKey]
		next_obj = response.get('_links', {}).get('next', {})
		next_page = None if next_obj is None else next_obj.get('href')
		while next_page:
			headers = self._authentication_headers()
			logger.debug(f'{method} {next_page}')
			r = getattr(requests, method)(next_page, headers=headers)
			if r.ok:
				response = r.json()
				if isinstance(response[EmbeddedKey], list):
					for item in response[EmbeddedKey]:
						yield item
				else:
					yield response[EmbeddedKey]
				next_obj = response.get('_links', {}).get('next', {})
				next_page = None if next_obj is None else next_obj.get('href')
			elif r.status_code == 401:
				self._authenticate()
			elif r.status_code == 429:
				self._handle_rate_limit_exceeded()
			else:
				raise HelpScoutException(r.text)

	def _authenticate(self):
		"""Authenticates with the API and gets a token for subsequent requests."""
		url = urljoin(self.base_url, 'oauth2/token')
		data = {
			'grant_type': 'client_credentials',
			'client_id': self.app_id,
			'client_secret': self.app_secret,
			}
		logger.debug(f'post {url}')
		r = requests.post(url, data=data, timeout=10)
		if r.ok:
			response = r.json()
			self.access_token = response['access_token']
		else:
			raise HelpScoutAuthenticationException(r.text)

	def _authentication_headers(self):
		"""Returns authentication headers."""
		if self.access_token is None:
			raise HelpScoutAuthenticationException('Tried to get access_token without prior authentication')
		return {
			'Authorization': 'Bearer ' + self.access_token,
			'content-type': 'application/json',
			'charset': 'UTF-8',
			}

	def _handle_rate_limit_exceeded(self):
		"""Handles a rate limit exceeded."""
		logger.warning('Rate limit exceeded.')
		if self.sleep_on_rate_limit_exceeded:
			time.sleep(self.rate_limit_sleep)
		else:
			raise HelpScoutRateLimitExceededException

	def __eq__(self, other):
		"""Equality comparison."""
		return (
			self.__class__ is other.__class__ and
			self.app_id == other.app_id and
			self.app_secret == other.app_secret and
			self.base_url == other.base_url and
			self.rate_limit_sleep == other.rate_limit_sleep and
			self.access_token == other.access_token and
			self.sleep_on_rate_limit_exceeded ==
			other.sleep_on_rate_limit_exceeded)

	def __repr__(self) -> str:
		"""Returns the object as a string."""
		name = self.__class__.__name__
		attrs = (
			'app_id', 'base_url', 'rate_limit_sleep',
			'sleep_on_rate_limit_exceeded')
		values = [getattr(self, attr) for attr in attrs]
		values = [
			f'"{value}"' if isinstance(value, str) else value
			for value in values]
		kwargs = ', '.join(
			f'{attr}={value}' for attr, value in zip(attrs, values))
		token = '"xxxxxx"' if self.access_token is not None else None
		return f'{name}({kwargs}, token={token})'

	__str__ = __repr__


class HelpScoutEndpointRequester:

	def __init__(self, client: HelpScout, endpoint: str, specific_resource: bool) -> None:
		"""Client wrapper to perform requester.get/post/put/patch/delete.

		Parameters
		----------
		client: HelpScout
			A help scout client instance to query the API.
		endpoint: str
			One of the endpoints in the API. E.g.: conversations, mailboxes.
		specific_resource: bool
			Specifies if the current endpoint requester is for a single
			specific resource id or not.
		"""
		self.client = client
		self.endpoint = endpoint
		self.specific_resource = specific_resource

	@overload
	def __getattr__(self, method: Literal['get']) -> Callable: ...

	@overload
	def __getattr__(self, method: str) -> Callable | partial | HelpScoutEndpointRequester: ...

	def __getattr__(self, method: str) -> Callable | partial | HelpScoutEndpointRequester:
		"""Catches http methods like get, post, patch, put and delete.

		Returns a subrequester when methods not named after http methods are
		requested, as this are considered attributes of the main object, like
		tags of a conversation.

		Parameters
		----------
		method: str
			The http method to request to the API.

		Returns
		-------
		Callable - client.get_objects return value for the *get* method.
		partial - client.hit return value for other http named methods.
		HelpScoutEndpointRequester when other attributes are accessed, this is
			expected to be used mainly for subattributes of an endpoint or
			subendpoints of specific resources, like tags from a conversation.

		"""
		if method == 'get':
			return partial(
				self.client.get_objects,
				self.endpoint,
				specific_resource=self.specific_resource,
				)
		if method in ('head', 'post', 'put', 'delete', 'patch', 'connect',
						'options', 'trace'):
			return partial(self._yielded_function, method)
		return HelpScoutEndpointRequester(
			self.client,
			urljoin(self.endpoint + '/', str(method)),
			False,
			)

	def __getitem__(self, resource_id: int | str) -> HelpScoutEndpointRequester:
		"""Returns a second endpoint requester extending the endpoint to a specific resource_id or resource_name.

		This is intented to access things such as conversations tags or notes,
		whose url are like 'conversations/%s/tags' % conversation_id

		Parameters
		----------
		resource_id: int | str
			The resource id or attribute available in the API through a
			specific call.

		Returns
		-------
		HelpScoutEndpointRequester
			A second endpoint requester for the specific resource id of the
			main requester's endpoint.

		"""
		return HelpScoutEndpointRequester(
			self.client,
			urljoin(self.endpoint + '/', str(resource_id)),
			True,
			)

	def _yielded_function(self, method:str, *args, **kwargs):
		"""Calls a generator function and calls next.

		It is intended to be used with post, put, patch and delete which do not
		return objects, but as hit is a generator, still have to be nexted.

		Parameters
		----------
		*args: positional arguments
			Positional arguments after *method* to forward to client.hit .
		*kwargs: keyword arguments
			Keyword arguments after *method* to forward to client.hit.
		method: str
			Inherited

		Returns
		-------
		client.hit yielded value.

		"""
		return next(self.client.hit_(self.endpoint, method, *args, **kwargs))

	def __eq__(self, other):
		"""Equality comparison."""
		return (
			self.__class__ is other.__class__ and
			self.endpoint == other.endpoint and
			self.client == other.client)

	def __repr__(self) -> str:
		"""Returns the object as a string."""
		name = self.__class__.__name__
		return f'{name}(app_id="{self.client.app_id}", endpoint="{self.endpoint}")'

	__str__ = __repr__

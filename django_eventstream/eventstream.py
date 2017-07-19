import copy
from .event import Event
from .storage import EventDoesNotExist
from .eventresponse import EventResponse
from .utils import make_id, publish_event, publish_kick, \
	get_storage, get_authorizer

class EventPermissionError(Exception):
	def __init__(self, message, channels=[]):
		super(Exception, self).__init__(message)
		self.channels = copy.deepcopy(channels)

def send_event(channel, event_type, data, skip_user_ids=[]):
	storage = get_storage()

	if storage:
		e = storage.append_event(channel, event_type, data)
		pub_id = str(e.id)
		pub_prev_id = str(e.id - 1)
	else:
		pub_id = None
		pub_prev_id = None

	# TODO: set pub meta: skip_users=user_id1,user_id2,...
	publish_event(channel, event_type, data, pub_id, pub_prev_id)

def get_events(request, limit=100, user=None):
	resp = EventResponse()
	resp.is_recover = request.is_recover
	resp.user = user

	if len(request.channels) == 0:
		return resp

	limit_per_type = limit / len(request.channels)
	if limit_per_type < 1:
		limit_per_type = 1

	storage = get_storage()
	authorizer = get_authorizer()

	inaccessible_channels = []
	for channel in request.channels:
		if not authorizer.can_read_channel(user, channel):
			inaccessible_channels.append(channel)

	if len(inaccessible_channels) > 0:
		msg = 'Permission denied to channels: %s' % (
			', '.join(inaccessible_channels))
		raise EventPermissionError(msg, channels=inaccessible_channels)

	for channel in request.channels:
		reset = False

		last_id = request.channel_last_ids.get(channel)

		if storage:
			if last_id is not None:
				try:
					events = storage.get_events(
						channel,
						int(last_id),
						limit=limit_per_type)
				except EventDoesNotExist as e:
					reset = True
					events = []
					last_id = str(e.current_id)
			else:
				events = []
				last_id = str(storage.get_current_id(channel))
		else:
			events = []
			last_id = None

		resp.channel_items[channel] = events
		if last_id is not None:
			resp.channel_last_ids[channel] = last_id
		if reset:
			resp.channel_reset.add(channel)
	return resp

def get_current_event_id(channels):
	storage = get_storage()

	cur_ids = {}
	for channel in channels:
		cur_ids[channel] = str(storage.get_current_id(channel))

	return make_id(cur_ids)

def channel_permission_changed(user, channel):
	authorizer = get_authorizer()
	if not authorizer.can_read_channel(user, channel):
		user_id = user.id if user else 'anonymous'
		# TODO: set pub meta: require_sub=channel
		publish_kick(user_id)

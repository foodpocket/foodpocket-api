from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import VisitRecord, Restaurant, Account, TokenSystem, Pocket
from datetime import date
from uuid import UUID
from django.contrib.auth.hashers import make_password, check_password
from django.db.models import Count
from .utils import check_email


# should enable csrf at later time
@csrf_exempt
def registerAccount(request):
    """
        [POST] register a new account
        must: username, password, email
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        username = request.POST['username']
        password = request.POST['password']
        email = request.POST['email']
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    username, ok, errorMsg = Account.preprocessUsername(username)
    if not ok:
        return HttpResponse('Invalid request;' + errorMsg, status=400)

    ok, errorMsg = Account.validateEmail(email)
    if not ok:
        return HttpResponse('Invalid request;' + errorMsg, status=400)

    password = make_password(password)  # one-way hash + salt

    # validate parameters
    if Account.objects.filter(username=username).count() > 0:
        response['result'] = '409'
        response['message'] = 'Username has been already registered by others'
        return JsonResponse(response, status=409)

    if Account.objects.filter(email=email).count() > 0:
        response['result'] = '409'
        response['message'] = 'Email has been already registered by others'
        return JsonResponse(response, status=409)

    # create Account
    account = Account(
        username=username,
        password=password,
        email=email,
        status='active',  # TODO: before validate the email address, this should be inactive
    )
    account.save()

    account.initAccount()

    response['result'] = 'successful'
    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def loginAccount(request):
    """
        [POST] login an existed account
        must: username, password

        Note: frontend need to check "result" to determine the result of the execution
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        username = request.POST['username']
        password = request.POST['password']
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    username, ok, errorMsg = Account.preprocessUsername(username)
    if not ok:
        return HttpResponse('Invalid request;' + errorMsg, status=400)

    # query
    try:
        user = Account.objects.get(username=username)
    except Account.DoesNotExist:
        response['result'] = 'login failed'
        return JsonResponse(response)

    # conditioning
    if check_password(password, user.password):
        token = TokenSystem.generate_token()
        user.tokensystem_set.create(
            token=token,
            expire_time=timezone.now() + timezone.timedelta(days=1)
        )

        # fetch userdata (configs)
        last_pocket = user.pocket_set.order_by(
            '-last_use_time', '-create_time').first()

        response['result'] = 'successful'
        response['data'] = {
            'token': token,
            'last_pocket': last_pocket.brief()
        }

        user.last_login = timezone.now()
        user.save()
    else:
        response['result'] = 'login failed'

    return JsonResponse(response)


def getRestaurantList(request):
    """
        [GET] Get all restaurants (in last visited + last updated order) and visit records visited by a user
        must: user_token, pocket_uid
    """
    response = {'result': '', 'data': ''}
    if request.method != 'GET':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.GET['user_token']
        pocket_uid = request.GET['pocket_uid']
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        pocket = Pocket.objects.exclude(status=Pocket.Status.DELETED) \
            .get(uid=pocket_uid, owner=user)

        # update last use time
        pocket.last_use_time = timezone.now()
        pocket.save()
    except Pocket.DoesNotExist:
        return HttpResponse('Failed, Pocket not found', status=404)

    restaurantMap = dict()

    # init restaurant objects
    for restaurant in pocket.restaurant_set.exclude(status=Restaurant.Status.DELETED):

        restaurantMap[restaurant.uid] = {
            'restaurant_uid': restaurant.uid,
            'restaurant_name': restaurant.name,
            'visited': 0,
            'visit_dates': [],
            'last_update': restaurant.create_time,
            'status': restaurant.getStatusLabel(),
            'hide_until': restaurant.hide_until,
            'note': restaurant.note,
        }

    # group up all records and build a restaurant hashmap
    records = VisitRecord.objects.select_related('restaurant') \
        .filter(restaurant__pocket=pocket).exclude(status=VisitRecord.Status.DELETED) \
        .order_by('-visit_date', '-create_time')

    for record in records:
        # skip records which the belonging restaurant does not available (hide or deleted)
        if record.restaurant.uid not in restaurantMap:
            continue

        restaurantMap[record.restaurant.uid]['visited'] += 1
        restaurantMap[record.restaurant.uid]['visit_dates'].append(
            record.visit_date)

        # update last visit time for sorting
        if restaurantMap[record.restaurant.uid]['last_update'] < record.create_time:
            restaurantMap[record.restaurant.uid]['last_update'] = record.create_time

    # convert map to array
    restaurantList = list(restaurantMap.values())

    # reorder the list to last visited + last updated order
    restaurantList = sorted(
        restaurantList,
        key=lambda restaurant: (
            restaurant['visit_dates'][0] if len(
                restaurant['visit_dates']) > 0 else date.min,
            restaurant['last_update'],
        ),
        reverse=True  # large to small
    )

    response['data'] = restaurantList
    response['result'] = 'successful'
    return JsonResponse(response)


def getVisitRecords(request):
    """
        [GET] Get all visit records visited by a user
        must: user_token, pocket_uid
    """
    response = {'result': '', 'data': ''}
    if request.method != 'GET':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.GET['user_token']
        pocket_uid = request.GET['pocket_uid']
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        pocket = Pocket.objects.get(uid=pocket_uid, owner=user)
    except Pocket.DoesNotExist:
        return HttpResponse('Failed, Pocket not found', status=404)

    records = VisitRecord.objects.select_related('restaurant') \
        .filter(owner=user, restaurant__pocket=pocket) \
        .exclude(status=VisitRecord.Status.DELETED) \
        .order_by('-visit_date', '-create_time')

    response['data'] = [
        {
            'visitrecord_uid': record.uid,
            'restaurant_uid': record.restaurant.uid,
            'restaurant_name': record.restaurant.name,
            'visit_date': record.visit_date,
            'create_time': record.create_time,
        } for record in records
    ]
    response['result'] = 'successful'
    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def newVisit(request):
    """
        [POST] Add new visit record
        must: user_token, restaurant_uid
        optional: visit_date, score
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        restaurant_uid = UUID(request.POST['restaurant_uid'], version=4)
        visit_date = request.POST.get('visit_date', '')
        score = int(request.POST.get('score', '3'))
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    if (visit_date == ''):
        visit_date = date.today()  # backend timezone awared
    else:
        try:
            visit_date = date.fromisoformat(visit_date)  # date from front end
        except ValueError:
            return HttpResponse('Invalid request; Wrong date format, should be YYYY-MM-DD', status=400)

    score = max(min(score, 5), 1)  # 1 <= score <= 5

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        restaurant = Restaurant.objects.get(uid=restaurant_uid, owner=user)
    except Restaurant.DoesNotExist:
        return HttpResponse('Failed, restaurant not found', status=404)

    # create record
    restaurant.visitrecord_set.create(
        owner=user,
        visit_date=visit_date,
        score=score,
    )
    response['result'] = 'successful'

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def editVisitRecord(request):
    """
        [POST] edit existed visit record
        must: user_token, visitrecord_uid, visit_date
        optional: score
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        visitrecord_uid = UUID(request.POST['visitrecord_uid'], version=4)
        visit_date = request.POST['visit_date']
        score = int(request.POST.get('score', '3'))
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    try:
        visit_date = date.fromisoformat(visit_date)  # date from front end
    except ValueError:
        return HttpResponse('Invalid request; Wrong date format, should be YYYY-MM-DD', status=400)

    score = max(min(score, 5), 1)  # 1 <= score <= 5

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        record = VisitRecord.objects.get(uid=visitrecord_uid, user=user)
    except VisitRecord.DoesNotExist:
        return HttpResponse('Failed, Visit Record not found', status=404)

    # create record
    record.visit_date = visit_date
    record.save()

    response['result'] = 'successful'

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def removeVisitRecord(request):
    """
        [POST] remove existed visit record
        must: user_token, visitrecord_uid
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        visitrecord_uid = UUID(request.POST['visitrecord_uid'], version=4)
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        record = VisitRecord.objects.get(uid=visitrecord_uid, owner=user)
    except VisitRecord.DoesNotExist:
        return HttpResponse('Failed, Visit Record not found', status=404)

    # fake remove record
    record.status = VisitRecord.Status.DELETED
    record.save()

    response['result'] = 'successful'

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def newRestaurant(request):
    """
        [POST] Add new restaurant
        must: name, user_token, pocket_uid
        optional: longitude, latitude, address, note
    """
    response = {'result': '', 'data': ''}

    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        rest_name = request.POST['name']
        user_token = request.POST['user_token']
        pocket_uid = request.POST['pocket_uid']
        longitude = request.POST.get('longitude', 0.0)
        latitude = request.POST.get('latitude', 0.0)
        address = request.POST.get('address', '')
        note = request.POST.get('note', '')
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    rest_name = rest_name[:200]
    address = address[:200]
    note = note[:1000]

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        pocket = Pocket.objects.get(uid=pocket_uid, owner=user)
    except Pocket.DoesNotExist:
        return HttpResponse('Failed, Pocket not found', status=404)

    # check whether the restaurant name already exists (created by the same user before)
    existRest = Restaurant.objects.filter(
        owner=user, name=rest_name).exclude(status=Restaurant.Status.DELETED)
    if existRest.count() != 0:  # use old one
        restaurant = existRest[0]
    else:  # create new one
        restaurant = Restaurant(
            name=rest_name,
            owner=user,
            pocket=pocket,
            longitude=longitude,
            latitude=latitude,
            address=address,
            note=note,
        )
        restaurant.save()

    response['result'] = 'successful'
    response['data'] = {'restaurant_uid': restaurant.uid}

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def editRestaurant(request):
    """
        [POST] edit existed restaurant
        must: user_token, restaurant_uid
        optional: name, longitude, latitude, address, note, status, hide_until
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        restaurant_uid = UUID(request.POST['restaurant_uid'], version=4)
        rest_name = request.POST.get('name', None)
        note = request.POST.get('note', None)
        statusStr = request.POST.get('status', None)
        hide_until = request.POST.get('hide_until', None)
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        restaurant = Restaurant.objects.get(uid=restaurant_uid, owner=user)
    except Restaurant.DoesNotExist:
        return HttpResponse('Failed, Restaurant not found', status=404)

    # preprocess parameters
    if rest_name is not None:
        ok, msg = restaurant.editName(rest_name)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    if note is not None:
        ok, msg = restaurant.editNote(note)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    if statusStr is not None:
        ok, msg = restaurant.editStatus(statusStr)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    if hide_until is not None:
        ok, msg = restaurant.editHideUntil(hide_until)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    restaurant.save()

    response['result'] = 'successful'

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def removeRestaurant(request):
    """
        [POST] remove existed restaurant
        must: user_token, restaurant_uid
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        restaurant_uid = UUID(request.POST['restaurant_uid'], version=4)
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        restaurant = Restaurant.objects.get(uid=restaurant_uid, owner=user)
    except Restaurant.DoesNotExist:
        return HttpResponse('Failed, Restaurant not found', status=404)

    # fake remove restaurant
    restaurant.status = Restaurant.Status.DELETED
    restaurant.save()

    # also mark all visit records (related to this restaurant) as DELETED
    for record in restaurant.visitrecord_set.all():
        record.status = VisitRecord.Status.DELETED
        record.save()

    response['result'] = 'successful'

    return JsonResponse(response)


def getPocketList(request):
    """
        [GET] Get all Pockets owned by a user
        must: user_token
    """
    response = {'result': '', 'data': ''}
    if request.method != 'GET':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.GET['user_token']
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    pockets = Pocket.objects.annotate(Count('restaurant')).filter(owner=user) \
        .exclude(status=Pocket.Status.DELETED) \
        .order_by('create_time')

    response['data'] = [
        {
            "pocket_uid": pocket.uid,
            "name": pocket.name,
            'size': pocket.restaurant__count
        } for pocket in pockets
    ]
    response['result'] = 'successful'
    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def newPocket(request):
    """
        [POST] Add new Pocket
        must: name, user_token
        optional: copy_restaurants, deep_copy_restaurants, note
    """
    response = {'result': '', 'data': ''}

    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        name = request.POST['name']
        user_token = request.POST['user_token']
        # copy_restaurants = json.loads(request.POST.get('init_restaurants', '\{\}'))
        note = request.POST.get('note', '')
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # preprocess parameters
    name = name[:200]
    note = note[:1000]

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    pocket = Pocket(
        name=name,
        owner=user,
        note=note,
    )
    pocket.save()

    response['result'] = 'successful'
    response['data'] = {'pocket_uid': pocket.uid}

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def editPocket(request):
    """
        [POST] edit existed Pocket (mainly for rename now)
        must: user_token, pocket_uid
        optional: name, note, status
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        pocket_uid = UUID(request.POST['pocket_uid'], version=4)
        name = request.POST.get('name', None)
        note = request.POST.get('note', None)
        statusStr = request.POST.get('status', None)
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        pocket = Pocket.objects.get(uid=pocket_uid, owner=user)
    except Pocket.DoesNotExist:
        return HttpResponse('Failed, Pocket not found', status=404)

    # preprocess parameters
    if name is not None:
        ok, msg = pocket.editName(name)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    if note is not None:
        ok, msg = pocket.editNote(note)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    if statusStr is not None:
        ok, msg = pocket.editStatus(statusStr)
        if not ok:
            return HttpResponse('Invalid request; ' + msg, status=400)

    pocket.save()

    response['result'] = 'successful'

    return JsonResponse(response)


# should enable csrf at later time
@ csrf_exempt
def removePocket(request):
    """
        [POST] remove existed Pocket
        must: user_token, pocket_uid
    """
    response = {'result': '', 'data': ''}
    if request.method != 'POST':
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # collect parameters
    try:
        user_token = request.POST['user_token']
        pocket_uid = UUID(request.POST['pocket_uid'], version=4)
    except (KeyError, ValueError):
        return HttpResponse('Invalid request; read document for correct parameters', status=400)

    # query foreign keys
    try:
        user = TokenSystem.objects.get(
            token=user_token, expire_time__gte=timezone.now()).owner
    except TokenSystem.DoesNotExist:
        return HttpResponse('Unauthorized, please login', status=401)

    try:
        pocket = Pocket.objects.get(uid=pocket_uid, owner=user)
    except Pocket.DoesNotExist:
        return HttpResponse('Failed, Pocket not found', status=404)

    # fake remove restaurant
    pocket.status = Pocket.Status.DELETED
    pocket.save()

    response['result'] = 'successful'

    return JsonResponse(response)

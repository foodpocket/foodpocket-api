from django.db import models
from django.utils import timezone
from django.db.models import Max
import uuid
import random
import string
from datetime import date, timedelta
from django.utils.translation import gettext_lazy as _
import re
from random import randrange


# Create your models here.
class Account (models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    username = models.CharField(max_length=64)
    password = models.CharField(max_length=256)
    email = models.EmailField(max_length=256)
    status = models.CharField(max_length=64)

    last_login = models.DateTimeField(default=timezone.now)
    create_time = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        ''' On save, update timestamps '''
        if not self.username:
            self.create_time = timezone.now()
        return super(Account, self).save(*args, **kwargs)

    def __str__(self):
        return self.username

    def initAccount(self):
        """
            initialize account configs and resources
            including:
            1. create a empty pocket
        """
        mypocket = Pocket(owner=self, name="My Pocket")
        mypocket.save()

    @staticmethod
    def preprocessUsername(username: str) -> (str, bool, str):
        """
            validate and preprocess username inputed by user

            return
            1. processed username
            2. is valid?
            3. error message
        """

        # check length
        if len(username) > 64:
            return None, False, "Username length exceed 64 characters"

        # check chars, only allow a-zA-Z0-9
        validChars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0987654321"
        for char in username:
            if char not in validChars:
                return None, False, "Username contains invalid character(s)"

        # transfer all chars to lowercase
        name = str.lower(username)

        return name, True, ""

    @staticmethod
    def validateEmail(email: str) -> (bool, str):
        """
            validate email inputed by user

            return
            1. is email valid?
            2. error message
        """
        isValid = re.match(r'[^@]+@[^@]+\.[^@]+', email)
        errorMsg = None if (isValid) else "Email format is invalid"
        return isValid, errorMsg


class TokenSystem (models.Model):
    owner = models.ForeignKey(Account, on_delete=models.CASCADE)

    token = models.CharField(max_length=256, unique=True)
    expire_time = models.DateTimeField()

    status = models.CharField(max_length=64, default="active")
    create_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.owner) + "/" + str(self.expire_time)

    @staticmethod
    def generate_token(length: int = 160) -> str:
        """
            Generate random token with provided length
        """
        return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(length))


class Pocket (models.Model):

    class Meta:
        verbose_name = _("Pocket")
        verbose_name_plural = _("Pockets")

    class Status(models.IntegerChoices):
        # user can always see this pocket in pocket list
        ACTIVE = 1, _('ACTIVE')

        # user can never see this pocket in pocket list (even in search)
        DELETED = 999, _('DELETED')

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    create_time = models.DateTimeField(default=timezone.now)
    last_use_time = models.DateTimeField(null=True, blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)
    note = models.CharField(max_length=1000, default="", blank=True)

    def __str__(self):
        return self.name

    def editStatus(self, newStatusLabel: str) -> (bool, str):
        # cannot change status once a pocket is deleted
        if self.status == self.Status.DELETED:
            return False, "Cannot edit status for deleted pocket"

        try:
            newStatus = self.Status[newStatusLabel].value
            self.status = newStatus

        except KeyError:
            return False, "Undefined status"

        return True, ""

    def editNote(self, newNote: str) -> (bool, str):
        self.note = newNote[:1000]
        return True, ""

    def editName(self, newName: str) -> (bool, str):
        if newName == '':
            return False, "Name field cannot be empty"

        newName = newName[:200]

        self.name = newName
        return True, ""

    def brief(self) -> dict():
        return {
            "pocket_uid": self.uid,
            "name": self.name,
        }

    def remove(self):
        """
            fake remove a pocket and all relavant restaurants and visit records
        """
        self.status = Pocket.Status.DELETED
        self.save()

        # remove restaurants
        for restaurant in self.restaurant_set.exclude(status=Restaurant.Status.DELETED):
            restaurant.remove()

    def getRestaurants(self):
        return self.restaurant_set.exclude(status=Restaurant.Status.DELETED)

    def getVisitRecords(self):
        return VisitRecord.objects.select_related('restaurant') \
            .filter(restaurant__pocket=self).exclude(status=VisitRecord.Status.DELETED) \
            .order_by('-visit_date', '-create_time')

    def getRecommandList(self):
        visibleList = self.restaurant_set \
            .exclude(status=Restaurant.Status.DELETED) \
            .exclude(hide_until__gt=date.today()) \
            .order_by('last_visit', 'create_time')

        recommandList = []
        randThreshold = 50  # 50/100
        # rule: only recommand a restaurant visited less than 5 times in past 30 days
        visitLimitIn30Days = 5
        # rule: only recommand a restaurant visited less than 2 times in past 7 days
        visitLimitIn7Days = 2
        for rest in visibleList:
            records = rest.getVisitRecords()
            if records.filter(visit_date__gt=date.today() - timedelta(days=30)).count() < visitLimitIn30Days \
                    and records.filter(visit_date__gt=date.today() - timedelta(days=7)).count() < visitLimitIn7Days:

                if rest.status == Restaurant.Status.ACTIVE:
                    # rule: always recommand an ACTIVE restaurant
                    recommandList.append(rest)
                elif rest.status == Restaurant.Status.RANDOM:
                    # rule: use random to decide whether recommand a RANDOM restaurant
                    if randrange(1, 100) > randThreshold:
                        recommandList.append(rest)

        return recommandList


class Restaurant (models.Model):

    class Status(models.IntegerChoices):
        # user can always see this restaurant in restaurant list
        ACTIVE = 1, _('ACTIVE')

        # sometimes do not show this restaurant
        RANDOM = 2, _('RANDOM')

        # NEVER use this status, this status is for frontend
        # don't update status while the new status is HIDE
        # for HIDE state, the hide_until will handle it
        HIDE = 3, _('HIDE')

        # user can never see this restaurant in restaurant list (even in search)
        DELETED = 999, _('DELETED')

        @staticmethod
        def strToStatusCode(statusString: str) -> int:
            if statusString == "ACTIVE":
                return Restaurant.Status.ACTIVE
            elif statusString == "DELETED":
                return Restaurant.Status.DELETED
            elif statusString == "RANDOM":
                return Restaurant.Status.RANDOM
            else:  # default
                return Restaurant.Status.RANDOM

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    pocket = models.ForeignKey(Pocket, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    longitude = models.FloatField(default=0.0)
    latitude = models.FloatField(default=0.0)
    address = models.CharField(max_length=200, default="", blank=True)
    create_time = models.DateTimeField(default=timezone.now)
    last_visit = models.DateField(null=True, blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.RANDOM)
    hide_until = models.DateField(default=date.today)  # check this with status
    note = models.CharField(max_length=1000, default="", blank=True)

    def __str__(self):
        return self.name

    def getStatusLabel(self) -> str:
        # handling cases for hide_until, return a special status "HIDE" for frond-end
        if self.status != self.Status.DELETED and self.hide_until > date.today():
            return self.Status.HIDE.label
        else:
            return self.Status(self.status).label

    def editStatus(self, newStatusLabel: str) -> (bool, str):
        # cannot change status once a restaurant is deleted
        if self.status == self.Status.DELETED:
            return False, "Cannot edit status for deleted restaurant"

        try:
            newStatus = self.Status[newStatusLabel].value
            if newStatus != self.Status.HIDE:
                # don't update status while the new status is HIDE
                # for HIDE state, the hide_until will handle it
                self.status = newStatus

                # also reset hide_until to today
                self.editHideUntil(str(date.today()))
        except KeyError:
            return False, "Undefined status"

        return True, ""

    def editNote(self, newNote: str) -> (bool, str):
        self.note = newNote[:1000]
        return True, ""

    def editName(self, newName: str) -> (bool, str):
        if newName == '':
            return False, "Name field cannot be empty"

        newName = newName[:200]

        if self.name == newName:
            return True, ""
        elif Restaurant.objects.filter(owner=self.owner, name=newName) \
                .exclude(status=Restaurant.Status.DELETED).count() != 0:
            return False, "Repeated Name"

        self.name = newName
        return True, ""

    def editHideUntil(self, newHideUntil: str) -> (bool, str):
        try:
            self.hide_until = date.fromisoformat(
                newHideUntil)  # should be YYYY-MM-DD format
        except ValueError:
            return False, "Wrong hide_until format, should be YYYY-MM-DD"

        return True, ""

    def remove(self):
        """
            fake remove a restaurant and all relavant visit records
        """
        self.status = Restaurant.Status.DELETED
        self.save()

        # remove visit records
        for record in self.visitrecord_set.exclude(status=VisitRecord.Status.DELETED):
            record.remove()

    def updateLastVisit(self):
        self.last_visit = self.getVisitRecords() \
            .aggregate(Max('visit_date'))['visit_date__max']
        self.save()

    def addVisitRecord(self, visit_date, score):
        self.visitrecord_set.create(
            owner=self.owner,
            visit_date=visit_date,
            score=score,
        )

        # update last_visit
        self.updateLastVisit()

    def getVisitRecords(self):
        return self.visitrecord_set.exclude(status=VisitRecord.Status.DELETED)

    def brief(self):
        last_update = self.create_time
        if self.last_visit and self.last_visit > self.create_time.date():
            last_update = self.last_visit

        return {
            'restaurant_uid': self.uid,
            'restaurant_name': self.name,
            'visit_count': self.getVisitRecords().count(),
            'last_visit': self.last_visit if self.last_visit else "",
            'last_update': last_update,
            'status': self.getStatusLabel(),
            'hide_until': self.hide_until,
            'note': self.note,
        }


class VisitRecord (models.Model):

    class Status(models.IntegerChoices):
        ACTIVE = 1      # user can always see this record
        DELETED = 2     # user can never see this record

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    owner = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    visit_date = models.DateField('visit date')
    create_time = models.DateTimeField(default=timezone.now)
    score = models.IntegerField(default=3)
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)

    def __str__(self):
        return str(self.owner) + '/' + str(self.restaurant) + '/' + str(self.visit_date)

    def remove(self):
        """
            fake remove a visit record
        """
        self.status = VisitRecord.Status.DELETED
        self.save()

        self.restaurant.updateLastVisit()

    def edit(self, visit_date):
        self.visit_date = visit_date
        self.save()

        self.restaurant.updateLastVisit()

from django.test import TestCase, Client
from restaurant.models import Restaurant, VisitRecord, Account, TokenSystem, Pocket
from django.utils import timezone
from datetime import date
import json
import uuid
from django.contrib.auth.hashers import check_password, make_password

tester_data = {
    'username': 'tester',
    'password': '321123321123',
    'email': 'tester@test.com',
}


class RestaurantApiTestCase(TestCase):
    def setUp(self):
        self.c = Client()

        # create account
        self.tester = Account(
            username=tester_data['username'],
            password=make_password(tester_data['password']),
            email=tester_data['email'],
        )
        self.tester.save()
        self.tester.initAccount()

        # create token
        self.token = TokenSystem.generate_token()
        self.tester.tokensystem_set.create(
            token=self.token,
            expire_time=timezone.now() + timezone.timedelta(days=1)
        )

        self.myPocket = self.tester.pocket_set.first()

        self.myRest = Restaurant(
            owner=self.tester,
            pocket=self.myPocket,
            name='my restaurant',
            note='this is my restaurant',
        )
        self.myRest.save()

        self.myVisit = VisitRecord(
            restaurant=self.myRest,
            owner=self.tester,
            visit_date=date.today(),
        )
        self.myVisit.save()

        self.visitCount = 1

    def test_add_new_pocket(self):
        """
            Basic functional test from newPocket api
        """
        data = {
            'name': 'my new pocket',
            'user_token': self.token,
        }
        res = self.c.post('/api/rest/newPocket/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        content = json.loads(res.content)['data']
        self.assertEqual(Pocket.objects.get(
            uid=content['pocket_uid']).name, data['name'])

    def test_edit_pocket(self):
        """
            Basic functional test from editPocket api
        """
        data = {
            'name': 'pocket2',
            'pocket_uid': self.myPocket.uid,
            'user_token': self.token,
        }
        res = self.c.post('/api/rest/editPocket/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        self.assertEqual(Pocket.objects.get(
            uid=self.myPocket.uid).name, data['name'])

    def test_remove_pocket(self):
        """
            Basic test to remove a pocket
        """
        data = {
            'user_token': self.token,
            'pocket_uid': self.myPocket.uid,
        }
        res = self.c.post('/api/rest/removePocket/', data)

        # TEST1: remove last one pocket
        self.assertEqual(403, res.status_code)

        # TEST2: basic remove pocket, remove one of two pockets
        self.tester.pocket_set.create(
            name='2nd pocket',
        )

        res = self.c.post('/api/rest/removePocket/', data)
        # test status code
        self.assertEqual(200, res.status_code)

        # check whether the name has updated in database
        self.assertEqual(
            Pocket.objects.get(owner=self.tester,
                               uid=data['pocket_uid']).status,
            Pocket.Status.DELETED
        )

    def test_add_new_restaurant(self):
        """
            @brief: Basic functional test for newRestaurant api
            @target: newRestaurant
        """
        data = {
            'name': 'abc restaurant',
            'note': 'a good restaurant, good to eat',
            'user_token': self.token,
            'pocket_uid': self.myPocket.uid
        }
        res = self.c.post('/api/rest/newRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # test whether the api correctly added record to database
        # and check fields data match the request's data
        content = json.loads(res.content)['data']
        self.assertEqual(Restaurant.objects.get(
            uid=content['restaurant_uid']).name, data['name'])
        self.assertEqual(Restaurant.objects.get(
            uid=content['restaurant_uid']).note, data['note'])

        # PART 2
        # after deleting the restaurant
        # add the restaurant with the same name should get a different uid
        res = self.c.post('/api/rest/removeRestaurant/', {
            'restaurant_uid': content['restaurant_uid'],
            'user_token': self.token,
        })
        self.assertEqual(200, res.status_code)

        res = self.c.post('/api/rest/newRestaurant/', data)

        new_content = json.loads(res.content)['data']
        self.assertNotEqual(content['restaurant_uid'],
                            new_content['restaurant_uid'])

    def test_add_duplicate_restaurant(self):
        """
            Try to add a restaurant with the same name as restaurant created before by the same user
        """
        data = {
            'name': self.myRest.name,  # same name
            'user_token': self.token,  # same user
            'pocket_uid': self.myPocket.uid
        }
        res = self.c.post('/api/rest/newRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # the api should not create a new restaurant instead of returning existed one
        content = json.loads(res.content)['data']
        self.assertEqual(content['restaurant_uid'], str(self.myRest.uid))
        self.assertEqual(Restaurant.objects.filter(
            owner=self.tester, name=data['name']).count(), 1)

    def test_edit_restaurant(self):
        """
            Basic test to edit a restaurant
        """
        data = {
            'name': "NEW NAME RESTAURANT",
            'note': 'a good restaurant, good to eat',
            'hide_until': '2100-12-01',
            'status': 'RANDOM',
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # check whether the name has updated in database
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).name,
            data['name']
        )

        # check wherther the note has updated in database
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).note,
            data['note']
        )

        # check wherther the hide_until has updated in database
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).hide_until,
            date.fromisoformat(data['hide_until'])
        )

        # check wherther the status has updated in database
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            Restaurant.Status[data['status']].value
        )

        """ edit single entry """
        # test name
        data = {
            'name': "NEW NAME RESTAURANT 2",
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).name,
            data['name']
        )

        # test note
        data = {
            'note': 'AAAAAAAAAAA',
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).note,
            data['note']
        )

        # test hide_until
        data = {
            'hide_until': '2018-12-11',
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).hide_until,
            date.fromisoformat(data['hide_until'])
        )

        # test status
        data = {
            'status': 'ACTIVE',
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            Restaurant.Status[data['status']].value
        )

    def test_hide_restaurant(self):
        """
            Tests to hide a restaurant
        """
        # original data
        originalStatus = Restaurant.objects.get(
            uid=self.myRest.uid).status

        """ First test: hide a restaurant by hide_until """
        data = {
            'hide_until': '2100-12-01',
            'status': 'HIDE',
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # the restaurant status should not become HIDE status
        self.assertNotEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            Restaurant.Status.HIDE
        )

        # the restaurant status should be the same as status before sending the request
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            originalStatus
        )

        # myRest should become HIDE status in the perspective of frontend
        # TODO: test with json

        """ Second test, set hide_until to today to disable hiding """
        data = {
            'hide_until': date.today(),
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/editRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # the restaurant status should be the same as status before sending the request
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            originalStatus
        )

        # myRest should be originalStatus instead of HIDE in the perspective of frontend
        # TODO: test with json

    def test_remove_restaurant(self):
        """
            Basic test to remove a restaurant
        """
        data = {
            'user_token': self.token,
            'restaurant_uid': self.myRest.uid,
        }
        res = self.c.post('/api/rest/removeRestaurant/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # check whether the name has updated in database
        self.assertEqual(
            Restaurant.objects.get(owner=self.tester,
                                   uid=data['restaurant_uid']).status,
            Restaurant.Status.DELETED
        )

        # check whether removed visit records related to the removed restaurant
        self.assertEqual(0, VisitRecord.objects.select_related(
            'restaurant').filter(restaurant=self.myRest).exclude(status=VisitRecord.Status.DELETED).count())

    def test_remove_visit(self):
        """
            Test Basic removing a visit record
        """
        data = {
            'user_token': self.token,
            'visitrecord_uid': self.myVisit.uid,
        }
        res = self.c.post('/api/rest/removeVisitRecord/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # test the result message
        result = json.loads(res.content)['result']
        self.assertEqual('successful', result)

        # test whether the api correctly added record to database
        record = VisitRecord.objects.get(
            uid=data['visitrecord_uid'], owner=self.tester)
        self.assertEqual(record.status, VisitRecord.Status.DELETED)

    def test_visit(self):
        """
            @brief: Basic functional test for newVisit api
            @target: newVisit
        """
        data = {
            'restaurant_uid': self.myRest.uid,
            'user_token': self.token,
        }
        res = self.c.post('/api/rest/newVisit/', data)
        self.visitCount += 1

        # test status code
        self.assertEqual(200, res.status_code)

        # test the result message
        result = json.loads(res.content)['result']
        self.assertEqual('successful', result)

        # test whether the api correctly added record to database
        vrList = VisitRecord.objects.filter(
            restaurant=self.myRest, owner=self.tester)
        self.assertEqual(len(vrList), self.visitCount)

        # repeat for extra 4 times
        repeat = 4
        for _ in range(repeat):
            res = self.c.post('/api/rest/newVisit/', data)
            self.visitCount += 1

        # test whether the api correctly added record to database
        vrList = VisitRecord.objects.filter(
            restaurant=self.myRest, owner=self.tester)
        self.assertEqual(len(vrList), self.visitCount)

    def test_visit_error(self):
        """
            @brief: Error testing for newVisit api
            @target: newVisit
        """

        # empty params
        res = self.c.post('/api/rest/newVisit/', {})
        self.assertEqual(400, res.status_code)

        # empty user_token
        res = self.c.post('/api/rest/newVisit/', {
            'restaurant_uid': self.myRest.uid,
        })
        self.assertEqual(400, res.status_code)

        # empty rest uid
        res = self.c.post('/api/rest/newVisit/', {
            'user_token': self.token,
        })
        self.assertEqual(400, res.status_code)

        res = self.c.post('/api/rest/newVisit/', {
            'restaurant_uid': 'abc',            # type error, should be UUID
            'user_token': self.token,           # correct
        })
        self.assertEqual(400, res.status_code)

        res = self.c.post('/api/rest/newVisit/', {
            'restaurant_uid': uuid.uuid4(),     # spec is correct, but not found
            'user_token': self.token,           # correct
        })
        self.assertEqual(404, res.status_code)

        res = self.c.post('/api/rest/newVisit/', {
            'restaurant_uid': self.myRest.uid,              # correct
            'user_token': TokenSystem.generate_token(),     # spec is correct, but not found
        })
        self.assertEqual(401, res.status_code)

    def test_new_restaurant_error(self):
        pass


class AccountApiTestCase(TestCase):
    def setUp(self):
        self.c = Client()

        self.tester = Account(
            username=tester_data['username'],
            password=make_password(tester_data['password']),
            email=tester_data['email'],
        )
        self.tester.save()
        self.tester.initAccount()

        # create token
        self.token = TokenSystem.generate_token()
        self.tester.tokensystem_set.create(
            token=self.token,
            expire_time=timezone.now() + timezone.timedelta(days=1)
        )

    def test_preprocess_username(self):
        """
            Unit test for preprocessUsername static function
        """
        validChars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0987654321"

        # TEST1
        for i in range(0, 256):
            before = chr(i)
            after, ok, errorMsg = Account.preprocessUsername(before)
            self.assertEqual(before in validChars, ok)

        # TEST2
        aftername, ok, errorMsg = Account.preprocessUsername("中文測試")
        self.assertEqual(False, ok)

    def test_registry(self):
        """
            Basic test for registerAccount api

            @target: registerAccount
        """
        data = {
            'username': 'hello',
            'password': 'helloworld_and_tester',
            'email': 'hello@test.com',
        }
        res = self.c.post('/api/rest/registerAccount/', data)

        # test status code
        self.assertEqual(200, res.status_code)

        # test the result message
        result = json.loads(res.content)['result']
        self.assertEqual('successful', result)

        # test whether the api correctly added record to database, and the password is correct
        user = Account.objects.get(username=data['username'])
        self.assertTrue(check_password(data['password'], user.password))
        self.assertEqual(user.email, data['email'])

    def test_registry_filter(self):
        """
            Test for registerAccount api with invalid username and invalid email

            @target: registerAccount
        """
        accountCount = Account.objects.all().count()
        data = {
            'username': 'hello',
            'password': 'helloworld_and_tester',
            'email': 'hello@test.com',
        }

        # TEST1: name with quote
        data['username'] = "xyz\"\'"
        data['email'] = "email1@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(400, res.status_code)
        self.assertEqual(accountCount, Account.objects.all().count())

        # TEST2: name with space
        data['username'] = "xyz "
        data['email'] = "email2@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(400, res.status_code)
        self.assertEqual(accountCount, Account.objects.all().count())

        # TEST3: name with special char
        data['username'] = "!@#xyz"
        data['email'] = "email3@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(400, res.status_code)
        self.assertEqual(accountCount, Account.objects.all().count())

        # TEST4: number started name
        data['username'] = "123xyz"
        data['email'] = "email4@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(accountCount + 1, Account.objects.all().count())
        accountCount += 1

        # TEST5: complex name
        data['username'] = "xyzXYZsdX123"
        data['email'] = "email5@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(200, res.status_code)
        self.assertEqual(accountCount + 1, Account.objects.all().count())
        accountCount += 1

        # TEST6: username conflict
        data['username'] = "xyzXYZsdX123"
        data['email'] = "email6@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(409, res.status_code)
        self.assertEqual(accountCount, Account.objects.all().count())

        # TEST7: email conflict
        data['username'] = "abc"
        data['email'] = "email5@email.com"
        res = self.c.post('/api/rest/registerAccount/', data)
        self.assertEqual(409, res.status_code)
        self.assertEqual(accountCount, Account.objects.all().count())

    def test_login_account(self):
        """
            Basic test for loginAccount api
        """

        data = {
            'username': tester_data["username"],
            'password': tester_data["password"],
        }

        res = self.c.post('/api/rest/loginAccount/', data)
        self.assertEqual(200, res.status_code)

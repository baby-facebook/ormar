import databases
import pytest
import sqlalchemy

import orm
from tests.settings import DATABASE_URL

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class Department(orm.Model):
    __tablename__ = "departments"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True, autoincrement=False)
    name = orm.String(length=100)


class SchoolClass(orm.Model):
    __tablename__ = "schoolclasses"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(length=100)
    department = orm.ForeignKey(Department, nullable=False)


class Category(orm.Model):
    __tablename__ = "categories"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(length=100)


class Student(orm.Model):
    __tablename__ = "students"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(length=100)
    schoolclass = orm.ForeignKey(SchoolClass)
    category = orm.ForeignKey(Category, nullable=True)


class Teacher(orm.Model):
    __tablename__ = "teachers"
    __metadata__ = metadata
    __database__ = database

    id = orm.Integer(primary_key=True)
    name = orm.String(length=100)
    schoolclass = orm.ForeignKey(SchoolClass)
    category = orm.ForeignKey(Category, nullable=True)


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)


@pytest.fixture()
async def init_relation():
    department = await Department.objects.create(id=1, name="Math Department")
    class1 = await SchoolClass.objects.create(name="Math", department=department)
    category = await Category.objects.create(name="Foreign")
    category2 = await Category.objects.create(name="Domestic")
    await Student.objects.create(name="Jane", category=category, schoolclass=class1)
    await Student.objects.create(name="Jack", category=category2, schoolclass=class1)
    await Teacher.objects.create(name="Joe", category=category2, schoolclass=class1)
    yield
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.drop_all(engine)
    metadata.create_all(engine)


@pytest.mark.asyncio
async def test_model_multiple_instances_of_same_table_in_schema(init_relation):
    async with database:
        classes = await SchoolClass.objects.select_related(
            ["teachers__category", "students"]
        ).all()
        assert classes[0].name == "Math"
        assert classes[0].students[0].name == "Jane"

        # related fields of main model are only populated by pk
        # unless there is a required foreign key somewhere along the way
        # since department is required for schoolclass it was pre loaded (again)
        # but you can load them anytime
        assert classes[0].students[0].schoolclass.name == "Math"
        assert classes[0].students[0].schoolclass.department.name is None
        await classes[0].students[0].schoolclass.department.load()
        assert classes[0].students[0].schoolclass.department.name == "Math Department"


@pytest.mark.asyncio
async def test_right_tables_join(init_relation):
    async with database:
        classes = await SchoolClass.objects.select_related(
            ["teachers__category", "students"]
        ).all()
        assert classes[0].teachers[0].category.name == "Domestic"

        assert classes[0].students[0].category.name is None
        await classes[0].students[0].category.load()
        assert classes[0].students[0].category.name == "Foreign"


@pytest.mark.asyncio
async def test_multiple_reverse_related_objects(init_relation):
    async with database:
        classes = await SchoolClass.objects.select_related(
            ["teachers__category", "students"]
        ).all()
        assert classes[0].name == "Math"
        assert classes[0].students[1].name == "Jack"
        assert classes[0].teachers[0].category.name == "Domestic"
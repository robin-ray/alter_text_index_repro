# Django Alter CharField/TextField Bug Reproduction

## Context

Django creates two indexes for CharFields and TextFields that have `db_index=True`. The second index has the same name
as the first but ends with `_like` and uses PostgreSQL's varchar_pattern_ops or text_pattern_ops.

## Bug

Django drops the existing `_like` index when an indexed CharField becomes a TextField (and vice versa), but Django
does not recreate the `_like` index with the new pattern ops. This behavior exists in Django 5.0.2 and earlier.

## Requirements

- Python 3.12
- Pipenv
- PostgreSQL 14

## Setup

1. Clone this repository
2. `cd` to the repository root
3. Run `pipenv install` to install dependencies
4. Run `pipenv shell` to activate the virtual environment
5. Run `export DJANGO_SETTINGS_MODULE=config.settings`
6. Create a new database called `app` in your postgres database
7. Run `./manage.py migrate` to execute all database migrations

## Reproduction

Commit [603cdcf](https://github.com/robin-ray/alter_text_index_repro/commit/603cdcf) adds the initial post model.

```sql
$ ./manage.py sqlmigrate app 0001
BEGIN;
--
-- Create model Post
--
CREATE TABLE "app_post" ("id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY, "title" varchar(100) NOT NULL, "content" text NOT NULL);
COMMIT;
```

Commit [3fc0c17](https://github.com/robin-ray/alter_text_index_repro/commit/3fc0c17) adds indexes to each field on the
post model. Here we can see the two indexes that are created for each field, including the `_like` index with pattern
ops.

```sql
$ ./manage.py sqlmigrate app 0002
BEGIN;
--
-- Alter field content on post
--
CREATE INDEX "app_post_content_8dcc9397" ON "app_post" ("content");
CREATE INDEX "app_post_content_8dcc9397_like" ON "app_post" ("content" text_pattern_ops);
--
-- Alter field title on post
--
CREATE INDEX "app_post_title_f6ecae13" ON "app_post" ("title");
CREATE INDEX "app_post_title_f6ecae13_like" ON "app_post" ("title" varchar_pattern_ops);
COMMIT;
```

We can verify that the indexes exist in the database with the following SQL:

```sql
select tablename, indexname, indexdef from pg_indexes where tablename = 'app_post';
```

| tablename | indexname                      | indexdef                                                                                              |
| --------- | ------------------------------ | ----------------------------------------------------------------------------------------------------- |
| app_post  | app_post_pkey                  | CREATE UNIQUE INDEX app_post_pkey ON public.app_post USING btree (id)                                 |
| app_post  | app_post_content_8dcc9397      | CREATE INDEX app_post_content_8dcc9397 ON public.app_post USING btree (content)                       |
| app_post  | app_post_content_8dcc9397_like | CREATE INDEX app_post_content_8dcc9397_like ON public.app_post USING btree (content text_pattern_ops) |
| app_post  | app_post_title_f6ecae13        | CREATE INDEX app_post_title_f6ecae13 ON public.app_post USING btree (title)                           |
| app_post  | app_post_title_f6ecae13_like   | CREATE INDEX app_post_title_f6ecae13_like ON public.app_post USING btree (title varchar_pattern_ops)  |

Commit [2d4de0c](https://github.com/robin-ray/alter_text_index_repro/commit/2d4de0c) changes the types of each field on
the post model (CharField to TextField and vice versa). Here we can see that the existing `_like` indexes gets dropped,
but they do not get recreated.

```sql
./manage.py sqlmigrate app 0003
BEGIN;
--
-- Alter field content on post
--
DROP INDEX IF EXISTS "app_post_content_8dcc9397_like";
ALTER TABLE "app_post" ALTER COLUMN "content" TYPE varchar(100) USING "content"::varchar(100);
--
-- Alter field title on post
--
DROP INDEX IF EXISTS "app_post_title_f6ecae13_like";
ALTER TABLE "app_post" ALTER COLUMN "title" TYPE text USING "title"::text;
COMMIT;
```

[434851b](https://github.com/robin-ray/alter_text_index_repro/commit/434851b) reverts the fields of the post model back
to their original types. Once again the `_like` indexes would be dropped without being recreated, but they do not exist
at this point anyway.

```sql
./manage.py sqlmigrate app 0004
BEGIN;
--
-- Alter field content on post
--
DROP INDEX IF EXISTS "app_post_content_8dcc9397_like";
ALTER TABLE "app_post" ALTER COLUMN "content" TYPE text USING "content"::text;
--
-- Alter field title on post
--
DROP INDEX IF EXISTS "app_post_title_f6ecae13_like";
ALTER TABLE "app_post" ALTER COLUMN "title" TYPE varchar(100) USING "title"::varchar(100);
COMMIT;
```

At this point, the model is in the same state as when we added the indexes in [3fc0c17](https://github.com/robin-ray/alter_text_index_repro/commit/3fc0c17).
However, the database is in a different state because it no longer contains the `_like` indexes for each field. We can
verify this by running the following SQL query:

```sql
select tablename, indexname, indexdef from pg_indexes where tablename = 'app_post';
```

| tablename | indexname                 | indexdef                                                                        |
| --------- | ------------------------- | ------------------------------------------------------------------------------- |
| app_post  | app_post_pkey             | CREATE UNIQUE INDEX app_post_pkey ON public.app_post USING btree (id)           |
| app_post  | app_post_content_8dcc9397 | CREATE INDEX app_post_content_8dcc9397 ON public.app_post USING btree (content) |
| app_post  | app_post_title_f6ecae13   | CREATE INDEX app_post_title_f6ecae13 ON public.app_post USING btree (title)     |

We can't simply migrate back to before the column type change migration because Django does not recreate the indexes in
the reverse SQL either:

```sql
./manage.py sqlmigrate app 0003 --backwards
BEGIN;
--
-- Alter field title on post
--
DROP INDEX IF EXISTS "app_post_title_f6ecae13_like";
ALTER TABLE "app_post" ALTER COLUMN "title" TYPE varchar(100) USING "title"::varchar(100);
--
-- Alter field content on post
--
DROP INDEX IF EXISTS "app_post_content_8dcc9397_like";
ALTER TABLE "app_post" ALTER COLUMN "content" TYPE text USING "content"::text;
COMMIT;
```
CREATE USER bookwheel_admin WITH PASSWORD '1234';

CREATE DATABASE bookwheel OWNER bookwheel_admin;

GRANT ALL ON SCHEMA public TO bookwheel_admin;

\c bookwheel bookwheel_admin

\i /rdb/ddl.sql
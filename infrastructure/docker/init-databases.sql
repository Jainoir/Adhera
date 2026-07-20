-- One database per service; services must never read another service's tables.
CREATE DATABASE identity;
CREATE DATABASE medication;
CREATE DATABASE notification;

#!/usr/bin/python3
# -*- coding: utf-8 -*-
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer, Float
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    current_selection=Column(String(255), nullable=True)
    keywords = relationship("Keywords", back_populates="user")
    counter=Column(Integer, nullable=True)

class Keywords(Base):
    __tablename__ = 'keywords'
    id = Column(Integer, primary_key=True)
    keywords = Column(String(250))
    category = Column(String(250))
    maxprice=Column(Float)
    scope=Column(Integer)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User", back_populates="keywords")
    
engine = create_engine('sqlite:///mydealz.sqlite')
Base.metadata.create_all(engine)	
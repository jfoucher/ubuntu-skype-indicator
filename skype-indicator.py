#!/usr/bin/env python
#
#Copyright 2010 Jonathan Foucher
#
#Authors:
#    Jonathan Foucher <jfoucher@6px.eu>
#
#This program is free software: you can redistribute it and/or modify it 
#under the terms of either or both of the following licenses:
#
#1) the GNU Lesser General Public License version 3, as published by the 
#Free Software Foundation; and/or
#2) the GNU Lesser General Public License version 2.1, as published by 
#the Free Software Foundation.
#
#This program is distributed in the hope that it will be useful, but 
#WITHOUT ANY WARRANTY; without even the implied warranties of 
#MERCHANTABILITY, SATISFACTORY QUALITY or FITNESS FOR A PARTICULAR 
#PURPOSE.  See the applicable version of the GNU Lesser General Public 
#License for more details.
#
#You should have received a copy of both the GNU Lesser General Public 
#License version 3 and version 2.1 along with this program.  If not, see 
#<http://www.gnu.org/licenses/>
#


import indicate
import gobject
import pynotify
import gtk
import hashlib
import Skype4Py
import urllib
import os


class skypeIndicator:
	notifShown={}
	oldcount={}
	count={}
	indicator={}

	def __init__(self):
		print "init:"

		#get skype control
		self.skype= Skype4Py.Skype()
		self.loadSkype()

		#create notification icon
		self.server = indicate.indicate_server_ref_default()
		self.server.set_type("message.im")
		self.server.set_desktop_file("/usr/share/applications/skype.desktop")
		self.server.connect("server-display", self.server_display)
		self.server.show()

		self.create_indicators()

	def loadSkype(self):
		print "loadSkype:"
		#Check that skype is running, otherwise - start it and wait for 5 secs
		try:
			if not self.skype.Client.IsRunning:
				self.skype.Client.Start()
		except:
			print "loadSkype: Starting up Skype"
			os.system("skype &")
			print "loadSkype: Waiting 10 seconds..."
			time.sleep(10)

		try:
			self.skype.Attach()
		except Skype4Py.errors.SkypeAPIError:
			print "loadSkype: Can't attach to Skype"

	def create_indicators(self):
		"""Loads skype messages, displays them as notification bubbles and also shows them in the messaging menu"""

		#initialize count dictionaries
		self.count={}
		#get unread messages from skype, set self.unread variable
		self.get_messages()

		#self.unread is a dictionary having the username of the sender or chat name as key and a list of messages as value
		for name in self.unread:
			# Here we look at the first message from this user to set the messaging menu indicator
			# we only want one indicator per user
			msg=self.unread[name][0]

			#initialize message count for this user
			if name not in self.count:
				self.count[name]=0
			if name not in self.oldcount:
				self.oldcount[name]=0

			# if this user doesn't have his indicator yet
			if name not in self.indicator:
				# create indicator
				self.indicator[name] = indicate.Indicator()
				print "create_indicators: creating indicator for %s" % name

				# Set indicator properties
				self.fullname=self.name_from_handle(name)
				self.indicator[name].set_property("subtype", "im")
				self.indicator[name].set_property("sender", self.fullname )
				self.indicator[name].set_property("handle", name)

				#this gets the most user-friendly name available for this user
				user=self.user_from_handle(name)

				#Prepare a filename
				self.file=os.path.join(os.path.expanduser("~/.cache/ubuntu-skype-indicator"), "%s.jpg" % self.fullname)

				# get an avatar for this user/chat
				try:
					# This will only work on windows
					user.SaveAvatarToFile(self.file)
				except:
					# So on linux we use a generated monster ID. Fun but useless!
					h=hashlib.md5(name).hexdigest()
					#TODO find a way to get skype avatars on linux
					urllib.urlretrieve('http://friedcellcollective.net/monsterid/monster/%s/64' % h, self.file)

				#convert the imge to a pixbuf
				pixbuf=gtk.gdk.pixbuf_new_from_file(self.file)
				# for use in the indicator
				self.indicator[name].set_property_icon("icon", pixbuf)

				# set the timestamp of the indicator (this is what makes the indicator display the time since the message was received
				self.indicator[name].set_property_time("time", msg.Timestamp)

				self.indicator[name].show()
				# when the user clicks on the indicator message, open the skype messaging window for this user
				self.indicator[name].connect("user-display", self.display_msg)
				
			msgbody = ''
			#reverse list so latest message is at the bottom
			for eachmsg in self.unread[name][::-1]:
				# msgbody contains all the messages from that user so far
				msgbody += eachmsg.Body + "\n"

			# We set this person's indicator body to the compound text
			self.indicator[name].set_property("body", msgbody)

			# if there are more than one message from this user, we set the indicator count to be displayed in the messaging menu.
			# Otherwise the time elapsed since receiving the message will be shown
			if self.count[name] > 1:
				self.indicator[name].set_property("count", str(self.count[name]))
			
			# If a new message arrived since last time checked, mark notification as not shown
			if self.count[name] > self.oldcount[name]:
				self.notifShown[name]=False

			#If notification marked as not shown, show it
			if not self.notifShown.get(name, False) and self.showNotification(self.fullname, msgbody, self.file):
				#mark notification as shown
				self.notifShown[name]=True

				self.indicator[name].set_property("draw-attention", "true")
				self.indicator[name].show()
				print "notification shown for", name

			print "%d messages from %s" %(self.count[name],name)
		# Set oldcountt variable for next loop
		self.oldcount=self.count
		# Loop runs as long as true is returned
		return True


	def name_from_handle(self,handle):
		print "name_from_handle for %s" % handle
		if '#' in handle:
			return self.skype.Chat(handle).FriendlyName
		else:
			user=self.skype.User(handle)
			if user.DisplayName:
				return user.DisplayName
			elif user.FullName:
				return user.FullName
			else:
				return handle

	def user_from_handle(self,handle):
		print "user_from_handle for %s" % handle
		if '#' in handle:
			return self.skype.Chat(handle)
		else:
			return self.skype.User(handle)

	def showNotification(self, title, message,file=None):
		'''takes a title and a message to display the email notification. Returns the
        created notification object'''

		n = pynotify.Notification(title, message, "notification-message-im")
		if file is not None:
			n.set_property("icon-name",os.getcwd() + "/" + file)
		n.show()

		return n

	def get_messages(self):
		print "checking messages"
		self.unread={}

		for msg in self.skype.MissedMessages:
			#Get number of people in chat
			chat_members = len(msg.Chat.Members)
			if (chat_members > 2):
				#Its a chat
				skype_name = msg.ChatName
				#print("Adding message in chat '%s' (%s), members: %s" % (msg.Chat.FriendlyName, msg.ChatName, chat_members))
			else:
				#User message
				skype_name = msg.FromHandle
				#print("Adding message from '%s' (%s)" % (msg.FromDisplayName, msg.FromHandle))

			if skype_name not in self.count:
				self.count[skype_name]=0
			if not skype_name in self.unread:
				self.unread[skype_name]=[]
			
			self.unread[skype_name].append(msg)
			self.count[skype_name]+=1
		return self.unread

	def server_display(self, widget, timestamp=None):
		#Show main Skype window
		self.skype.Client.Focus()

	def display_msg(self, indicator, timestamp):
		#hide this indicator
		indicator.hide()
		#messaging menu goes back to normal
		indicator.set_property("draw-attention", "false")
		# open the skype chat window for this user or chat
		handle = indicator.get_property("handle")
		if "#" in handle:
			self.skype.Client.OpenDialog('CHAT', handle);
		else:
			self.skype.Client.OpenMessageDialog(indicator.get_property("handle"))

if __name__ == "__main__":

	skypeind=skypeIndicator()

	# Loop
	gobject.timeout_add_seconds(5, skypeind.create_indicators)
	gtk.main()

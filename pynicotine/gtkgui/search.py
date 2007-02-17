# Copyright (c) 2003-2004 Hyriand. All rights reserved.
#
import gtk
import gobject

import re
import sre_constants
import locale
import string
import random

from pynicotine import slskmessages

from nicotine_glade import SearchTab
from utils import InitialiseColumns, PopupMenu, FastListModel, Humanize
from dirchooser import ChooseDir
from entrydialog import *
from pynicotine.utils import _

class Searches:
	def __init__(self, frame):
		self.frame = frame
		self.interval = 0
		self.searchid = int(random.random() * (2**31-1))
		self.searches = {}
		self.timer = None
		self.disconnected = 0
	
		frame.SearchNotebook.popup_enable()
		#frame.combo1.disable_activate()
		
		items = self.frame.np.config.sections["searches"]["history"]
		templist = []
		for i in items:
			if i not in templist:
				templist.append(i)
		for i in templist:
			self.frame.combo1.append_text(i)
		
	def SetInterval(self, msg):
		self.interval = 1000
		
		if not self.disconnected:
			for term in self.frame.np.config.sections["server"]["autosearch"]:
				self.CreateTab(self.searchid, term, 0, 1)
				self.searchid = (self.searchid + 1) % (2**31)
				
		
		self.OnAutoSearch()
		self.timer = gobject.timeout_add(self.interval*1000, self.OnAutoSearch)
	
	def ConnClose(self):
		self.disconnected = 1
		if self.timer is not None:
			gobject.source_remove(self.timer)
			self.timer = None
	
	def OnAutoSearch(self, *args):
		if self.interval == 0:
			return False
		
		searches = self.frame.np.config.sections["server"]["autosearch"]
		if not searches:
			return True
		
		term = searches.pop()
		searches.insert(0, term)
		
		for i in self.searches.values():
			if i[1] == term and i[4]:
				if i[2] == None:
					break
				self.DoGlobalSearch(i[0], term)
				break
		
		return True
	
	def OnClearSearchHistory(self):
		self.frame.SearchEntry.set_text("")
		self.frame.np.config.sections["searches"]["history"] = []
		self.frame.np.config.writeConfig()
		self.frame.combo1.get_model().clear()
	
	def OnSearch(self):
		text = self.frame.SearchEntry.get_text().strip()
		self.frame.SearchEntry.set_text("")
		if not text:
			return

		if self.frame.GlobalRadio.get_active():
			mode = 0
		elif self.frame.RoomsRadio.get_active():
			mode = 1
		else:
			mode = 2
		self.DoSearch(text, mode)
		
	def DoSearch(self, text, mode, users = []):
		items = self.frame.np.config.sections["searches"]["history"]
		if text in items:
			items.remove(text)
		items.insert(0, text)
		# Clear old items
		del items[15:]
		self.frame.np.config.writeConfig()
		# Repopulate the combo list
		self.frame.combo1.get_model().clear()
		templist = []
		for i in items:
			if i not in templist:
				templist.append(i)
		for i in templist:
			self.frame.combo1.append_text(i)
			
		self.CreateTab(self.searchid, text, mode)
		text = self.frame.np.encode(text)
		if mode == 0:
			self.DoGlobalSearch(self.searchid, text)
		elif mode == 1:
			self.DoRoomsSearch(self.searchid, text)
		elif mode == 2:
			self.DoBuddiesSearch(self.searchid, text)
		else:
			self.DoPeerSearch(self.searchid, text, users)
		self.searchid += 1
		
	def DoGlobalSearch(self, id, text):
		self.frame.np.queue.put(slskmessages.FileSearch(id, text))
	
	def DoRoomsSearch(self, id, text):
		for room in self.frame.chatrooms.roomsctrl.joinedrooms.keys():
			self.frame.np.queue.put(slskmessages.RoomSearch(room, id, text))


	def DoBuddiesSearch(self, id, text):
		for users in self.frame.userlist.userlist:
			self.frame.np.queue.put(slskmessages.UserSearch(users[0], id, text))

	
	def DoPeerSearch(self, id, text, users):
		for user in users:
			self.frame.np.ProcessRequestToPeer(user, slskmessages.FileSearchRequest(None,id,text))

	def CreateTab(self, id, text, mode, remember = False):
		tab = Search(self, text, id, mode, remember)

		if mode:
			label = "(" + ("", _("Rooms"), _("Buddies"), _("User"))[mode] + ") " + text[:15]
		else:
			label = text[:20]
		self.frame.SearchNotebook.append_page(tab.vbox7, label, tab.OnCloseIgnore)

		search = [id, text, tab, mode, remember]
		self.searches[id] = search
		return search
		
	def ShowResult(self, msg, username, country):
		if not self.searches.has_key(msg.token):
			return
		
		search = self.searches[msg.token]
		if search[2] == None:
			search = self.CreateTab(search[0], search[1], search[3], search[4])
		
		search[2].AddResult(msg, username, country)

	def RemoveAutoSearch(self, id):
		if not id in self.searches:
			return
		search = self.searches[id]
		if search[1] in self.frame.np.config.sections["server"]["autosearch"]:
			self.frame.np.config.sections["server"]["autosearch"].remove(search[1])
			self.frame.np.config.writeConfig()
		search[4] = 0
		
	def RemoveTab(self, tab):
		if self.searches.has_key(tab.id):
			search = self.searches[tab.id]
			search[2] = None
			if search[4]:
				self.RemoveAutoSearch(search[0])
		
		self.frame.SearchNotebook.remove_page(tab.vbox7)

	def AutoSearch(self, id):
		if not self.searches.has_key(id):
			return
		i = self.searches[id]
		if i[1] in self.frame.np.config.sections["server"]["autosearch"]:
			return
		self.frame.np.config.sections["server"]["autosearch"].append(i[1])
		self.frame.np.config.writeConfig()
		i[4] = 1
		
	def UpdateColours(self):
		for id in self.searches.values():
			id.ChangeColours()
			
class SearchTreeModel(FastListModel):
	COLUMNS = 14
	COLUMN_TYPES = [gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,
    			gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,
    			gobject.TYPE_INT, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_INT, gobject.TYPE_INT]

	def __init__(self):
		FastListModel.__init__(self)
		self.all_data = []
		self.filters = None
		self.sort_col = 1
		self.sort_order = gtk.SORT_DESCENDING
		
	def append(self, results):
		ix = len(self.all_data) + 1
		l = len(self.data)
		returned = 0
		
		for r in results:
			size = r[2]
			r[2] = Humanize(size)
			speed = r[3]
			r[3] = Humanize(speed)
			queue = r[4]
			r[4] = Humanize(queue)
			row = [ix] + r + [size, speed, queue]
			self.all_data.append(row)
			if not self.filters or self.check_filter(row):
				self.data.append(row)
				iter = self.get_iter((l,))
				self.row_inserted((l,), iter)
				l += 1
				returned += 1
			ix += 1
		
		return returned

	def sort(self):
		col = self.sort_col
		order = self.sort_order
		if col == 3:
			col = 13
		elif col == 4:
			col = 14
		elif col == 5:
			col = 15

		if self.COLUMN_TYPES[col] == gobject.TYPE_STRING:
			compare = locale.strcoll
		else:
			compare = cmp

		if order == gtk.SORT_ASCENDING:
			self.data.sort(lambda r1,r2: compare(r1[col], r2[col]))
			self.all_data.sort(lambda r1,r2: compare(r1[col], r2[col]))
		else:
			self.data.sort(lambda r2,r1: compare(r1[col], r2[col]))
			self.all_data.sort(lambda r2,r1: compare(r1[col], r2[col]))

	def checkDigit(self, filter, value, factorize = True):
		op = ">="
		if filter[:1] in (">", "<", "="):
			op, filter = filter[:1]+"=", filter[1:]

		if not filter:
			return True

		factor = 1
		if factorize:
			if filter.lower()[-1] == "g":
				factor = 1024*1024*1024
				filter = filter[:-1]
			elif filter.lower()[-1] == "m":
				factor = 1024*1024
				filter = filter[:-1]
			elif filter.lower()[-1] == "k":
				factor = 1024
				filter = filter[:-1]

		if not filter:
			return True

		if not filter.isdigit():
			return True

		filter = long(filter) * factor

		if eval(str(value)+op+str(filter), {}):
			return True

		return False

	def check_filter(self, row):
		filters = self.filters
		if filters[0] and not filters[0].search(row[1].lower()):
			return False
		if filters[1] and filters[1].search(row[1].lower()):
			return False
		if filters[2] and not self.checkDigit(filters[2], row[13]):
			return False
		if filters[3] and not self.checkDigit(filters[3], row[10], False):
			return False
		if filters[4] and row[6] != "Y":
			return False
		if filters[5]:
			for cc in filters[5]:
				if not cc:
					continue
				if cc[0] == "-":
					if row[12] == cc[1:]:
						return False
				elif cc != row[12]:
					return False
		return True
	
	def set_filters(self, enable, f_in, f_out, size, bitrate, freeslot, country):
		if not enable:
			self.filters = None
			self.data = self.all_data[:]
			return
		self.filters = [None, None, None, None, freeslot, None]
		
		if f_in:
			try:
				f_in = re.compile(f_in.lower())
				self.filters[0] = f_in
			except sre_constants.error:
				pass
		
		if f_out:
			try:
				f_out = re.compile(f_out.lower())
				self.filters[1] = f_out
			except sre_constants.error:
				pass
		
		if size:
			self.filters[2] = size
		
		if bitrate:
			self.filters[3] = bitrate

		if country:
			self.filters[5] = country.upper().split(" ")

		self.data = []
		for row in self.all_data:
			if self.check_filter(row):
				self.data.append(row)

class Search(SearchTab):
	def __init__(self, searches, text, id, mode, remember):
		SearchTab.__init__(self, False)

#		self.ResultsList.set_double_buffered(False)

		self.searches = searches
		self.frame = searches.frame
		self.text = text
		self.id = id
		self.mode = mode
		self.remember = remember
		self.users = []
		self.QueryLabel.set_text(text)

		self.resultsmodel = SearchTreeModel()

# 		self.FilterIn.disable_activate()
# 		self.FilterOut.disable_activate()
# 		self.FilterSize.disable_activate()
# 		self.FilterBitrate.disable_activate()
# 		self.FilterCountry.disable_activate()

		if self.frame.np.config.sections["searches"]["enablefilters"]:
			filter = self.frame.np.config.sections["searches"]["defilter"]
			self.FilterIn.child.set_text(filter[0])
			self.FilterOut.child.set_text(filter[1])
			self.FilterSize.child.set_text(filter[2])
			self.FilterBitrate.child.set_text(filter[3])
			self.FilterFreeSlot.set_active(filter[4])
			if(len(filter) > 5):
				self.FilterCountry.child.set_text(filter[5])
			self.checkbutton1.set_active(1)

		if mode > 0:
			self.RememberCheckButton.set_sensitive(False)
		self.RememberCheckButton.set_active(remember)

		self.selected_results = []
		self.selected_users = []

		self.ResultsList.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
		self.ResultsList.set_property("rules-hint", True)
		cols = InitialiseColumns(self.ResultsList,
			["", 20, "text", self.CellDataFunc],
			[_("Filename"), 250, "text", self.CellDataFunc],
			[_("User"), 100, "text", self.CellDataFunc],
			[_("Size"), 100, "text", self.CellDataFunc],
			[_("Speed"), 50, "text", self.CellDataFunc],
			[_("In queue"), 50, "text", self.CellDataFunc],
			[_("Immediate Download"), 20, "text", self.CellDataFunc],
			[_("Bitrate"), 50, "text", self.CellDataFunc],
			[_("Length"), 50, "text", self.CellDataFunc],
			[_("Directory"), 1000, "text", self.CellDataFunc],
		)
		self.ResultsList.set_model(self.resultsmodel)
		for ix in range(len(cols)):
			col = cols[ix]
			col.connect("clicked", self.OnResort, ix)
			for r in col.get_cell_renderers():
				r.set_fixed_height_from_font(1)
		self.OnResort(cols[0], 0)

		self.ResultsList.set_headers_clickable(True)
		
		self.popup_menu = popup = PopupMenu(self.frame)
		popup.setup(
			("#" + _("_Download file(s)"), self.OnDownloadFiles, gtk.STOCK_GO_DOWN),
			("#" + _("Download file(s) _to..."), self.OnDownloadFilesTo, gtk.STOCK_GO_DOWN),
			("#" + _("Download containing _folder(s)"), self.OnDownloadFolders, gtk.STOCK_GO_DOWN),
			("#" + _("View Metadata of file(s)"), self.OnSearchMeta, gtk.STOCK_PROPERTIES),
			("", None),
			("#" + _("Copy _URL"), self.OnCopyURL, gtk.STOCK_COPY),
			("#" + _("Copy folder URL"), self.OnCopyDirURL, gtk.STOCK_COPY),
			("", None),
			("#" + _("Send _message"), popup.OnSendMessage, gtk.STOCK_EDIT),
			("#" + _("Show IP a_ddress"), popup.OnShowIPaddress, gtk.STOCK_NETWORK),
			("#" + _("Get user i_nfo"), popup.OnGetUserInfo, gtk.STOCK_DIALOG_INFO),
			("#" + _("Brow_se files"), popup.OnBrowseUser, gtk.STOCK_HARDDISK),
			("#" + _("Gi_ve privileges"), popup.OnGivePrivileges, gtk.STOCK_JUMP_TO),
			("$" + _("_Add user to list"), popup.OnAddToList),
			("$" + _("_Ban this user"), popup.OnBanUser),
			("$" + _("_Ignore this user"), popup.OnIgnoreUser),
		)
		
		self.ResultsList.connect("button_press_event", self.OnListClicked)
		
		self._more_results = 0
		self.new_results = []
		self.ChangeColours()
		
	def ChangeColours(self):
		self.frame.SetTextBG(self.ResultsList)
		
	def SelectedResultsCallback(self, model, path, iter):
		user = model.get_value(iter, 2)
		fn = model.get_value(iter, 11)
		
		self.selected_results.append((user, fn))
		
		if not user in self.selected_users:
			self.selected_users.append(user)
	
	def OnListClicked(self, widget, event):
		if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
			self.selected_results = []
			self.selected_users = []
			self.ResultsList.get_selection().selected_foreach(self.SelectedResultsCallback)
			self.OnDownloadFiles(widget)
			self.ResultsList.get_selection().unselect_all();
			return True
		elif event.button == 3:
			return self.OnPopupMenu(widget, event)
		return False
		
	def OnPopupMenu(self, widget, event):
		if event.button != 3:
			return False
		
		self.selected_results = []
		self.selected_users = []
		self.ResultsList.get_selection().selected_foreach(self.SelectedResultsCallback)
		
		items = self.popup_menu.get_children()
		
		act = len(self.selected_results) and True or False
		for i in range(0, 4):
			items[i].set_sensitive(act)

		if len(self.selected_results) == 1:
			act = True
		else:
			act = False
		items[5].set_sensitive(act)
		items[6].set_sensitive(act)

		act = False
		if len(self.selected_users) == 1:
			act = True
			user = self.selected_users[0]
			self.popup_menu.set_user(user)
			items[13].set_active(user in [i[0] for i in self.frame.np.config.sections["server"]["userlist"]])
			items[14].set_active(user in self.frame.np.config.sections["server"]["banlist"])
			items[15].set_active(user in self.frame.np.config.sections["server"]["ignorelist"])
		
		for i in range(7, 16):
			items[i].set_sensitive(act)
		
		widget.emit_stop_by_name("button_press_event")
		self.popup_menu.popup(None, None, None, event.button, event.time)
		return True
		
	def AddResult(self, msg, user, country):
		if user in self.users:
			return
		self.users.append(user)
		
		results = []
		if msg.freeulslots:
			imdl = _("Y")
		else:
			imdl = _("N")
		ix = len(self.resultsmodel.data)
		decode = self.frame.np.decode
		for result in msg.list:
			name = result[1].split('\\')[-1]
			dir = result[1][:-len(name)]
			bitrate = ""
			length = ""
			br = 0
			if result[3] == "mp3" and len(result[4]) == 3:
				a = result[4]
				if a[2] == 1:
					bitrate = _(" (vbr)")
				bitrate = str(a[0]) + bitrate
				br = a[0]
				length = '%i:%02i' %(a[1] / 60, a[1] % 60)
			results.append([decode(name), user, result[2], msg.ulspeed, msg.inqueue, imdl, bitrate, length, decode(dir), br, result[1], country])
			ix += 1
			
		if results:
			self.new_results += results
			
			if self._more_results == 0:
				self._more_results = 1
				gobject.timeout_add(1000, self._realaddresults)
			else:
				self._more_results = 2
			return len(results)
	
	def _realaddresults(self):
		if self._more_results == 2:
			self._more_results = 1
			return True
		
		r = self.new_results
		self.new_results = []
		self._more_results = 0

		res = self.resultsmodel.append(r)

		if res:
			self.frame.SearchNotebook.request_changed(self.vbox7)
			self.frame.RequestIcon(self.frame.SearchTabLabel)

		rows = len(self.resultsmodel.data)
		for c in self.ResultsList.get_columns():
			for r in c.get_cell_renderers():
				r.set_fixed_height_from_font(1)

		return False
		
	def CellDataFunc(self, column, cellrenderer, model, iter):
		imdl = model.get_value(iter, 6)
		colour = imdl == _("Y") and "search" or "searchq"
		colour = self.frame.np.config.sections["ui"][colour] or None
		cellrenderer.set_property("foreground", colour)

	def MetaBox(self, title="Meta Data", message="", data=None, modal= True):
		win = MetaDialog( self.frame, message,  data, modal)
		win.set_title(title)
		win.set_icon(self.frame.images["n"])
		win.set_default_size(300, 100)
		win.show()
		gtk.main()
		return win.ret
	
	def SelectedResultsAllData(self, model, path, iter, data):
		num = model.get_value(iter, 0)
		filename = model.get_value(iter, 1)
		user = model.get_value(iter, 2)
		size = model.get_value(iter, 3)
		speed = model.get_value(iter, 4)
		queue = model.get_value(iter, 5)
		immediate = model.get_value(iter, 6)
		bitratestr = model.get_value(iter, 7)
		length = model.get_value(iter, 8)
		directory = model.get_value(iter, 9)
		#bitrate = model.get_value(iter, 10)
		fn = model.get_value(iter, 11)
		country = model.get_value(iter, 12)
		data[len(data)] = {"user":user, "fn": fn, "position":num, "filename":filename, "directory":directory, "size":size, "speed":speed, "queue":queue, "immediate":immediate, "bitrate":bitratestr, "length":length, "country":country}

			
	def OnSearchMeta(self, widget):
		if not self.frame.np.transfers:
			return
		data = {}
		self.ResultsList.get_selection().selected_foreach(self.SelectedResultsAllData, data)

		if data != {}:	
			self.MetaBox(title=_("Nicotine+: Search Results"), message=_("<b>Metadata</b> for Search Query: <i>%s</i>" % self.text), data=data, modal=True)
			
	def OnDownloadFiles(self, widget, prefix = ""):
		
		if not self.frame.np.transfers:
			return
		for file in self.selected_results:
			self.frame.np.transfers.getFile(file[0], file[1], prefix)
	
	def OnDownloadFilesTo(self, widget):
		dir = ChooseDir(self.frame.MainWindow, self.frame.np.config.sections["transfers"]["downloaddir"])
		if dir is None:
			return
		for dirs in dir:
			self.OnDownloadFiles(widget, dirs)
			break
	
	def OnDownloadFolders(self, widget):
		folders = []
		for i in self.selected_results:
			dir = string.join(i[1].split("\\")[:-1], "\\")
			if (i[0], dir) in folders:
				continue
			self.frame.np.ProcessRequestToPeer(i[0], slskmessages.FolderContentsRequest(None, dir))
			folders.append((i[0], dir))

	def OnCopyURL(self, widget):
		user, path = self.selected_results[0][:2]
		self.frame.SetClipboardURL(user, path)

	def OnCopyDirURL(self, widget):
		user, path = self.selected_results[0][:2]
		path = string.join(path.split("\\")[:-1], "\\") + "\\"
		self.frame.SetClipboardURL(user, path)
	
	def OnToggleFilters(self, widget):
		if widget.get_active():
			self.Filters.show()
			self.OnRefilter(None)
		else:
			self.Filters.hide()
			self.ResultsList.set_model(None)
			self.resultsmodel.set_filters(0, None, None, None, None, None, "")
			self.ResultsList.set_model(self.resultsmodel)

	def OnIgnore(self, widget):
		self.RememberCheckButton.set_active(0)
		self.RememberCheckButton.set_sensitive(0)
		self.OnToggleRemember(self.RememberCheckButton)

		if self.id in self.searches.searches.keys():
			del self.searches.searches[self.id]
		
		widget.set_sensitive(False)

	def OnClose(self, widget):
		self.searches.RemoveTab(self)
		self.OnCloseIgnore(widget)

	def OnCloseIgnore(self, widget):
		self.OnIgnore(self.button2)
		self.searches.RemoveTab(self)

	def OnToggleRemember(self, widget):
		self.remember = widget.get_active()
		if not self.remember:
			self.searches.RemoveAutoSearch(self.id)
		else:
			self.searches.AutoSearch(self.id)

	def PushHistory(self, widget, title):
		text = widget.child.get_text()
		if not text.strip():
        		return None
		history = self.frame.np.config.sections["searches"][title]
		self.frame.np.config.pushHistory(history, text, 5)
		widget.append_text( text)
		widget.child.set_text(text)
		return text
		
	def OnRefilter(self, widget):
		f_in = self.PushHistory(self.FilterIn, "filterin")
		f_out = self.PushHistory(self.FilterOut, "filterout")
		f_size = self.PushHistory(self.FilterSize, "filtersize")
		f_br = self.PushHistory(self.FilterBitrate, "filterbr")
		f_free = self.FilterFreeSlot.get_active()
		f_country = self.PushHistory(self.FilterCountry, "filtercc")
		
		self.ResultsList.set_model(None)
		self.resultsmodel.set_filters(1, f_in, f_out, f_size, f_br, f_free, f_country)
		self.ResultsList.set_model(self.resultsmodel)

	def OnResort(self, column, column_id):
		if self.resultsmodel.sort_col == column_id:
			order = self.resultsmodel.sort_order
			if order == gtk.SORT_ASCENDING:
				order = gtk.SORT_DESCENDING
			else:
				order = gtk.SORT_ASCENDING
			column.set_sort_order(order)
			self.resultsmodel.sort_order = order
			self.ResultsList.set_model(None)
			self.resultsmodel.sort()
			self.ResultsList.set_model(self.resultsmodel)
			return
		cols = self.ResultsList.get_columns()
		cols[self.resultsmodel.sort_col].set_sort_indicator(False)
		cols[column_id].set_sort_indicator(True)
		self.resultsmodel.sort_col = column_id
		self.OnResort(column, column_id)

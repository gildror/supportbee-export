import requests
import sqlite3 as lite
import sys
from StringIO import StringIO
import Image
import io

base_url = 'https://[[INSERT-COMPANY-NAME]].supportbee.com/'
auth_token = '[[INSERT-AUTH-TOKEN]]'

#get the total number of tickets
#more options here: https://developers.supportbee.com/api
response = requests.get("{0}/tickets?auth_token={1}&archived=any&per_page=1&page=1".format(base_url, auth_token), verify=False)
page = response.json()
total_tickets = page['total'] 


con = None
timeout = 60

try:

	#create or connect to an existing database
	con = lite.connect('supportbee.sqlite')

	with con:
	    
	    #create the db schema
	    cur = con.cursor()   
	    cur.execute("DROP TABLE IF EXISTS Tickets")
	    cur.execute("DROP TABLE IF EXISTS TicketAttachments")
	    cur.execute("DROP TABLE IF EXISTS Comments")
	    cur.execute("DROP TABLE IF EXISTS CommentAttachments")

	    cur.execute("CREATE TABLE Tickets(Id INT PRIMARY KEY ASC, SupportbeeID INT, Subject TEXT, CreationDate TEXT, CreatedBy TEXT, AssignedTo TEXT, Content TEXT, Label TEXT, Status TEXT)")
	    cur.execute("CREATE TABLE TicketAttachments(Id INT PRIMARY KEY ASC, TicketId INT, FileName TEXT, CreationDate TEXT, ContentType TEXT, Image BLOB)")
	    cur.execute("CREATE TABLE Comments(Id INT PRIMARY KEY ASC, TicketId INT, CreationDate TEXT, CreatedBy TEXT, Content TEXT)")
	    cur.execute("CREATE TABLE CommentAttachments(Id INT PRIMARY KEY ASC, CommentId INT, FileName TEXT, CreationDate TEXT, ContentType TEXT, Image BLOB)")
	    
	    con.text_factory = lite.OptimizedUnicode

	page_count = 1
	sql_ticket_id = 1
	sql_comment_id = 1
	sql_attachment_id = 1
	sql_c_attachment_id = 1


	#loop pages
	while (page_count <= total_tickets / 100):
		print 'getting page ' + str(page_count)
		response = requests.get("{0}/tickets?auth_token={1}&archived=any&per_page=100&page={2}".format(base_url, auth_token, str(page_count)), timeout=timeout, verify=False)
		page_json = response.json()
		page_count += 1
		
		#loop tickets
		tickets = page_json['tickets']
		for ticket in tickets:
			ticket_id = ticket["id"]
			print 'getting ticket ' + str(ticket_id)

			sql_subject = ticket['subject']
			sql_created_at = ticket['created_at']
			sql_email = ticket['requester']['email']
			sql_html = ticket['content']['html']

			sql_assigned_to = ''
			if ('current_assignee' in ticket):
				if ('user' in ticket['current_assignee']):
					sql_assigned_to = ticket['current_assignee']['user']['email']

			if (ticket['archived'] is False):
				sql_status = 'In Progress'
			else:
				sql_status = 'Closed'

			sql_label = 'imported'
			for l in ticket['labels']:
				sql_label += ',%s' % l['name']

			cur.execute("INSERT INTO Tickets VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", (int(sql_ticket_id), int(ticket_id), sql_subject, sql_created_at, sql_email, sql_assigned_to, sql_html, sql_label, sql_status))

			#get attachments for ticket
			attachments = ticket['content']['attachments']
			for attachment in attachments:
				print 'getting attachments for ticket ' + str(ticket_id)

				image_url = attachment['url']['original'] + '?auth_token={0}'.format(auth_token)
				image_response = requests.get(image_url, timeout=timeout, verify=False)
				image = image_response.content

				#debug: save image to file
				#with open(attachment['filename'], 'wb') as output_file:
				#	output_file.write(image)

				sql_att_content = lite.Binary(image)
				sql_att_file_name = attachment['filename']
				sql_att_created_date = attachment['created_at']
				sql_att_content_type = attachment['content_type']
				cur.execute("INSERT INTO TicketAttachments VALUES(?, ?, ?, ?, ?, ?)", (int(sql_attachment_id), int(sql_ticket_id), sql_att_file_name, sql_att_created_date, sql_att_content_type, sql_att_content))
				sql_attachment_id += 1


			#get comments for ticket
			print 'getting comments for ticket ' + str(ticket_id)
			comments_response = requests.get("{0}/tickets/{1}/comments?auth_token={2}".format(base_url, str(ticket_id), auth_token), timeout=timeout, verify=False)
			comments = comments_response.json()['comments']

			for comment in comments:
				#insert the comment to the db
				sql_c_created_date = comment['created_at']
				sql_c_created_by = comment['commenter']['email']
				sql_c_html = ticket['content']['html']
				cur.execute("INSERT INTO Comments VALUES(?, ?, ?, ?, ?)", (int(sql_comment_id), int(sql_ticket_id), sql_c_created_date, sql_c_created_by, sql_c_html))

				#get attachments for comment
				c_attachments = comment['content']['attachments']
				for attachment in c_attachments:
					print 'getting attachments for comment ' + str(sql_comment_id)
					image_url = attachment['url']['original'] + '?auth_token={0}'.format(auth_token)
					image_response = requests.get(image_url, timeout=timeout, verify=False)
					sql_att_content = lite.Binary(image_response.content)
					sql_att_file_name = attachment['filename']
					sql_att_created_date = attachment['created_at']
					sql_att_content_type = attachment['content_type']
					cur.execute("INSERT INTO CommentAttachments VALUES(?, ?, ?, ?, ?, ?)", (int(sql_c_attachment_id), int(sql_comment_id), sql_att_file_name, sql_att_created_date, sql_att_content_type, sql_att_content))
					sql_c_attachment_id += 1

				sql_comment_id += 1

			sql_ticket_id += 1
			con.commit()

	print 'done with no errors.'

except lite.Error, e:
    
    print "Error %s:" % e.args[0]
    sys.exit(1)
    
finally:

	if con:
		con.close()


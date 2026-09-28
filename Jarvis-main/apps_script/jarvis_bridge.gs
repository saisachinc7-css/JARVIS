/*
 * AntiGravity / JARVIS Google Apps Script Bridge
 * Deploy as Web App and set APPS_SCRIPT_URL in .env
 */

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents || "{}");
    var action = body.action || "";
    var params = body.params || {};

    var handlers = {
      test: testConnection,
      gmail_list_unread: gmailListUnread,
      gmail_search: gmailSearch,
      gmail_send: gmailSend,
      gmail_draft_reply: gmailDraftReply,
      gmail_summarize: gmailSummarize,
      gmail_detect_urgent: gmailDetectUrgent,
      drive_list_files: driveListFiles,
      drive_read_doc: driveReadDoc,
      drive_create_doc: driveCreateDoc,
      drive_rename_file: driveRenameFile,
      drive_move_file: driveMoveFile,
      drive_delete_file: driveDeleteFile,
      calendar_get_events: calendarGetEvents,
      calendar_create_event: calendarCreateEvent,
      tasks_list: tasksList,
      sheets_read: sheetsRead,
      sheets_write: sheetsWrite,
      sheets_append: sheetsAppend
    };

    if (!handlers[action]) {
      return jsonResponse({ status: "error", error: "Unknown action: " + action });
    }

    var data = handlers[action](params);
    return jsonResponse({ status: "success", action: action, data: data });
  } catch (err) {
    return jsonResponse({ status: "error", error: String(err) });
  }
}

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function testConnection() {
  return {
    message: "Apps Script bridge is running",
    timestamp: new Date().toISOString()
  };
}

function gmailListUnread(params) {
  var max = Number(params.limit || 10);
  var threads = GmailApp.search("is:unread", 0, max);
  return threads.map(function(t) {
    var m = t.getMessages()[0];
    return {
      threadId: t.getId(),
      subject: m.getSubject(),
      from: m.getFrom(),
      date: m.getDate()
    };
  });
}

function gmailSearch(params) {
  var q = params.query || "";
  if (params.from) q += " from:" + params.from;
  if (params.subject) q += " subject:(" + params.subject + ")";
  if (params.keyword) q += " " + params.keyword;
  q = q.trim() || "in:inbox";

  var max = Number(params.limit || 10);
  var threads = GmailApp.search(q, 0, max);
  return threads.map(function(t) {
    var m = t.getMessages()[0];
    return {
      threadId: t.getId(),
      subject: m.getSubject(),
      from: m.getFrom(),
      snippet: m.getPlainBody().slice(0, 200),
      date: m.getDate()
    };
  });
}

function gmailSend(params) {
  GmailApp.sendEmail(params.to, params.subject || "(No subject)", params.body || "", {
    cc: params.cc || "",
    bcc: params.bcc || ""
  });
  return { sent: true };
}

function gmailDraftReply(params) {
  var thread = GmailApp.getThreadById(params.threadId);
  if (!thread) throw new Error("Thread not found");
  thread.createDraftReply(params.replyText || "");
  return { drafted: true };
}

function gmailSummarize(params) {
  var period = String(params.period || "today");
  var query = period === "today" ? "newer_than:1d" : "newer_than:7d";
  var threads = GmailApp.search(query, 0, 20);
  return {
    period: period,
    count: threads.length,
    subjects: threads.map(function(t) { return t.getFirstMessageSubject(); })
  };
}

function gmailDetectUrgent() {
  var threads = GmailApp.search("is:unread (subject:urgent OR subject:asap OR \"high priority\")", 0, 20);
  return threads.map(function(t) {
    return {
      threadId: t.getId(),
      subject: t.getFirstMessageSubject()
    };
  });
}

function driveListFiles(params) {
  var limit = Number(params.limit || 20);
  var files = [];
  var iter = DriveApp.getFiles();
  while (iter.hasNext() && files.length < limit) {
    var f = iter.next();
    files.push({ id: f.getId(), name: f.getName(), mimeType: f.getMimeType() });
  }
  return files;
}

function driveReadDoc(params) {
  if (!params.docId) throw new Error("docId is required");
  var doc = DocumentApp.openById(params.docId);
  return { id: params.docId, title: doc.getName(), content: doc.getBody().getText() };
}

function driveCreateDoc(params) {
  var doc = DocumentApp.create(params.title || "Untitled Document");
  if (params.content) doc.getBody().setText(params.content);
  return { id: doc.getId(), title: doc.getName(), url: doc.getUrl() };
}

function driveRenameFile(params) {
  var file = DriveApp.getFileById(params.fileId);
  file.setName(params.newName || file.getName());
  return { renamed: true, id: file.getId(), name: file.getName() };
}

function driveMoveFile(params) {
  var file = DriveApp.getFileById(params.fileId);
  var folder = DriveApp.getFolderById(params.targetFolderId);
  folder.addFile(file);
  return { moved: true, fileId: file.getId(), folderId: folder.getId() };
}

function driveDeleteFile(params) {
  var file = DriveApp.getFileById(params.fileId);
  file.setTrashed(true);
  return { trashed: true, fileId: file.getId() };
}

function calendarGetEvents(params) {
  var cal = CalendarApp.getDefaultCalendar();
  var start = params.timeMin ? new Date(params.timeMin) : new Date();
  var end = params.timeMax ? new Date(params.timeMax) : new Date(Date.now() + 24 * 60 * 60 * 1000);
  var events = cal.getEvents(start, end);
  return events.map(function(e) {
    return {
      id: e.getId(),
      title: e.getTitle(),
      start: e.getStartTime(),
      end: e.getEndTime(),
      location: e.getLocation()
    };
  });
}

function calendarCreateEvent(params) {
  var cal = CalendarApp.getDefaultCalendar();
  var event = cal.createEvent(
    params.title || "Untitled Event",
    new Date(params.startTime),
    new Date(params.endTime),
    {
      description: params.description || "",
      location: params.location || ""
    }
  );
  return { id: event.getId(), title: event.getTitle() };
}

function tasksList(params) {
  var dueMin = params.dueMin ? new Date(params.dueMin) : new Date();
  var dueMax = params.dueMax ? new Date(params.dueMax) : new Date(Date.now() + 24 * 60 * 60 * 1000);
  var lists = Tasks.Tasklists.list().items || [];
  var out = [];

  lists.forEach(function(list) {
    var tasks = Tasks.Tasks.list(list.id, { showCompleted: false, maxResults: params.maxResults || 20 }).items || [];
    tasks.forEach(function(t) {
      if (!t.due) return;
      var due = new Date(t.due);
      if (due >= dueMin && due <= dueMax) {
        out.push({ list: list.title, id: t.id, title: t.title, due: t.due });
      }
    });
  });

  return out;
}

function sheetsRead(params) {
  var ss = SpreadsheetApp.openById(params.spreadsheetId);
  var sheet = ss.getSheetByName(params.sheetName || "Sheet1");
  var range = params.range || sheet.getDataRange().getA1Notation();
  return sheet.getRange(range).getValues();
}

function sheetsWrite(params) {
  var ss = SpreadsheetApp.openById(params.spreadsheetId);
  var sheet = ss.getSheetByName(params.sheetName || "Sheet1");
  var values = params.values || [[]];
  sheet.getRange(params.range).setValues(values);
  return { written: true, range: params.range };
}

function sheetsAppend(params) {
  var ss = SpreadsheetApp.openById(params.spreadsheetId);
  var sheet = ss.getSheetByName(params.sheetName || "Sheet1");
  (params.values || []).forEach(function(row) { sheet.appendRow(row); });
  return { appended: true, rows: (params.values || []).length };
}

/* emmaaFunctions.js - main javascript functions for the ASKE emmaa project

This file contains helper functions and project specific functions that does 
the client side work of exposing cancer network models for the end users

*/

// CONSTANTS AND IDs
var INDRA_ENGLISH_ASSEMBLY = "http://api.indra.bio:8000/assemblers/english";
var EMMMAA_BUCKET = 'emmaa';
var MODELS_ARRAY = ['aml',      // Acute myeloid leukemia
                    'brca',     // Breast Cancer
                    'luad',     // Lung adenocarcinoma
                    'paad',     // Pancreas adenocarcinoma
                    'prad',     // Prostate adenocarcinoma
                    'skcm',     // Skin cutaneous melanoma
                    'rasmodel', // RasModel
                    'test']     // TestModel (only three nodes/two edges)

function grabJSON (url, callback) {
  return $.ajax({url: url, dataType: "json"});
};

function _readCookie(cookieName) {
  console.log('function _readCookie()')
  var nameEQ = cookieName;
  var ca = document.cookie.split(';');
  for (var i = 0; i < ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) == 0) {
      console.log('function _readCookie() resolved cookie value ' + c.substring(nameEQ.length, c.length))
      return c.substring(nameEQ.length, c.length)
    };
  }
  console.log('function _readCookie() did not resolve cookie value')
  return;
}

function _writeCookie(cookieName, value, hours) {
  console.log('function _writeCookie(cookieName, value, hours)')
  if (hours) {
    let _hours = 0;
    maxHours = 12;
    if (hours > maxHours) {
      _hours = maxHours;
    } else {
      _hours = hours;
    } 
    // console.log('hours to expiration: ' + _hours)
    var date = new Date();
    date.setTime(date.getTime() + (_hours*60*60*1000))
    var expires = '; expires=' + date.toGMTString();
    // console.log('cookie expiration date: ' + date.toGMTString());
  } else var expires = '';  // No expiration or infinite?

  var cookieString = cookieName + value + expires + '; path=/'
  // console.log('cookieString: ' + cookieString);
  document.cookie = cookieString;
}

function getDictFromUrl(url) {
  // No url provided
  if (!url) return;
  var query = {};
  // Check if (authorization) code flow or token (implicit) flow
  if (url.split('#')[1]) {
    query = url.split('#')[1];
  } else if (url.split('?')[1]) {
    query = url.split('?')[1];
  } else return;
  
  var result = {};
  query.split("&").forEach(function(part) {
    var item = part.split("=");
    result[item[0]] = decodeURIComponent(item[1]);
  });
  return result;
}

function clearTables(arrayOfTableBodys) {
  for (tableBody of arrayOfTableBodys) {
    tableBody.innerHTML = null;
  }
}

// Creates a new two-column table row with the key value pair
function addToRow(col1, col2) {
  let tableRow = document.createElement('tr');

  column1 = document.createElement('td');
  column1.textContent = col1;
  tableRow.appendChild(column1);

  column2 = document.createElement('td');
  column2.textContent = col2;
  tableRow.appendChild(column2);
  
  return tableRow;
}

// CHANGE TEXT
function notifyUser(outputNode, outputText) {
  // Add other things here
  outputNode.textContent = outputText;
}

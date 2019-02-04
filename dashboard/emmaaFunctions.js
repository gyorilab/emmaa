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

function setModel(ddSelect, model) {
  // Sets the selected option
  // let ddSelect = document.getElementById('modelSelectDD');
  for (child of ddSelect.children) {
    if (model == child.value) {
      child.selected = 'selected';
      break;
    }
  }      
}

function selectModel(modelInfoTableBody, listTestResultsTableBody, testResultTableBody, ddSelect) {
  console.log('function selectModel(modelInfoTableBody, listTestResultsTableBody, testResultTableBody, ddSelect)')
  // Get selected option
  var model = '';
  for (child of ddSelect.children) {
    if (child.selected) {
      model = child.value;
      break;
    }
  }

  endsWith = '.json'
  maxKeys = 1000
  prefix = 'results';

  // List model info
  // FIXME add call to list model test

  // Pass tables, model and mode to function that lists the 
  listObjectsInBucketUnAuthenticated('listModelTests', listTestResultsTableBody, testResultTableBody, new AWS.S3(), EMMMAA_BUCKET, model, prefix, maxKeys, endsWith)
}

function loadModelMetaData(modelInfoTable, bucket, modelKey) {
  console.log('function loadModelMetaData(bucket, modelKey)')
  modelMetaInfoPromise = getPublicJson(bucket, modelKey)
  modelMetaInfoPromise.then(function(json) {
    populateModelsTable(modelInfoTable, json);
  });
}

function clearTables(arrayOfTableBodys) {
  for (tableBody of arrayOfTableBodys) {
    clearTable(tableBody)
  }
}

function clearTable(tableBody) {
  tableBody.innerHTML = null;
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

function populateModelsTable(metaTableBody, json) {
  console.log('function populateModelsTable(metaTableBody, json)')
  // console.log(json)
  clearTable(metaTableBody);

  // Get english statements from evidence text
  // Link out to restAPI html page with all statements
  let maxOutput = Math.min(json.length, 25)
  for (let i = 0; i < maxOutput; i++) {
    // console.log('Loop ' + i)
    let plainEnglish = json[i].stmt.evidence[0].text;
    let sourceHash = json[i].stmt.evidence[0].source_hash;
    link = document.createElement('a')
    if (sourceHash) {
      link.textContent = 'Evidence'
      link.href = 'https://lsm6zea7gg.execute-api.us-east-1.amazonaws.com/production/statements/from_hash/' + sourceHash + '?format=html' // rest api from hash
    } else {
      link.textContent = 'No evidence'
    }

    let tableRow = addToRow(plainEnglish, '')
    tableRow.children[1].innerHTML = null;
    tableRow.children[1].appendChild(link)

    metaTableBody.appendChild(tableRow);
  }
}

// Populate test results json to modelTestResultBody
function populateTestResultTable(tableBody, json) {
  console.log('function populateTestResultTable(tableBody, json)')
  console.log(json)
  clearTable(tableBody);

  // FIXME handle resultsjsons of length > 1
  var results = {};
  if (!json.result_json) {
    results = json[0].result_json;
    tableBody.appendChild(addToRow('Model Name', json[0].model_name));
    tableBody.appendChild(addToRow('Test Type', json[0].test_type));
  } else {
    results = json.result_json;
    tableBody.appendChild(addToRow('Model Name', json.model_name));
    tableBody.appendChild(addToRow('Test Type', json.test_type));
  }

  // Results contents: 
  // max_path_length: int (e.g. 5)
  // max_paths: int (e.g. 1)
  // path_found: bool (e.g. false)
  // path_metrics: Array []
  // paths: Array []
  // py/object: str (e.g. "indra.explanation.model_checker.PathResult")
  // result_code: str (e.g. "NO_PATHS_FOUND")
  tableBody.appendChild(addToRow('Max Path Length', results.max_path_length));
  tableBody.appendChild(addToRow('Max Paths', results.max_paths));
  tableBody.appendChild(addToRow('Path Found', results.path_found));
  tableBody.appendChild(addToRow('Number of Path Metrics', results.path_metrics.length));
  tableBody.appendChild(addToRow('Number of Paths', results.paths.length));
  tableBody.appendChild(addToRow('Results Code', results.result_code));
}

// CHANGE TEXT
function notifyUser(outputNode, outputText) {
  // Add other things here
  outputNode.textContent = outputText;
}

function getEnglishByJson(json_stmt_array) {
    eng_stmt = $.ajax({
        url: INDRA_ENGLISH_ASSEMBLY,
        type: "POST",
        dataType: "json",
        contentType: "application/json",
        data: JSON.stringify(json_stmt_array),
    });
    return eng_stmt
};

function sortByCol(arr, colIndex){
  arr.sort(sortFunction)
  function sortFunction(a, b) {
    a = a[colIndex]
    b = b[colIndex]
    return (a === b) ? 0 : (a < b) ? -1 : 1
  }
}

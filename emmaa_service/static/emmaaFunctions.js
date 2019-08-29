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
                    'marm_model', // MARM
                    'paad',     // Pancreas adenocarcinoma
                    'prad',     // Prostate adenocarcinoma
                    'rasmodel', // RasModel
                    'rasmachine', // Ras Machine
                    'skcm',     // Skin cutaneous melanoma
                    'test'];    // TestModel (only three nodes/two edges)

function grabPlainText (url, callback) {
  return $.ajax({url: url, dataType: "text"});
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
  // console.log('function selectModel(modelInfoTableBody, listTestResultsTableBody, testResultTableBody, ddSelect)')
  // Get selected option
  var model = '';
  for (child of ddSelect.children) {
    if (child.selected) {
      model = child.value;
      break;
    }
  }

  let endsWith = '.json';
  let maxKeys = MAX_KEYS;
  // Prefix needs to be precise enough that fewer than 1000 objects are returned
  //Example: stats/skcm/stats_2019-08-20-17-34-40.json
  let today = new Date();
  let currentYearMonth = today.toISOString().slice(0,7);
  let resultsPrefix = `stats/${model}/stats_${currentYearMonth}`;
  let s3Interface = new AWS.S3();

  // List model info

  // Pass tables, model and mode to function that lists the latest tests
  listObjectsInBucketUnAuthenticated('listModelTests', listTestResultsTableBody, testResultTableBody, s3Interface, EMMMAA_BUCKET, model, resultsPrefix, maxKeys, endsWith)
}

function loadModelMetaData(modelInfoTable, bucket, model, maxKeys, endsWith) {
  console.log('function loadModelMetaData(modelInfoTable, bucket, model, maxKeys, prefix, endsWith)')
  // wrapper function that can be called selectModel or from pageload of models.html

  // Prefix needs to be precise enough that fewer than 1000 objects are returned
  // example: models/aml/model_2018-12-13-18-11-54.pkl
  let today = new Date();
  let currentYearMonth = today.toISOString().slice(0,7);
  let s3Prefix = `models/${model}/model_${currentYearMonth}`;
  console.log('s3Prefix: ');
  console.log(s3Prefix);
  // mode, tableBody, testResultTableBody, s3Interface, bucket, model, prefix, maxKeys, endsWith
  // listObjectsInBucketUnAuthenticated('listModelInfo', modelInfoTable, null, new AWS.S3(), bucket, model, s3Prefix, maxKeys, endsWith)
}

function clearTables(arrayOfTableBodies) {
  for (tableBody of arrayOfTableBodies) {
    clearTable(tableBody)
  }
}

function clearTable(tableBody) {
  tableBody.innerHTML = null;
}

// Creates a new table row given an array of values
function addToRow(col_values) {
  let tableRow = document.createElement('tr');

  for (col of col_values) {
    column = document.createElement('td');
    column.textContent = col;
    tableRow.appendChild(column);
  }

  return tableRow;
}

function generatePassFail(rowEl, col) {
  // See more at:
  // https://fontawesome.com/icons?d=gallery
  // Pass: <i class="fas fa-check"></i>
  // Fail: <i class="fas fa-times"></i>
  let string = rowEl.children[col].textContent;
  let itag = document.createElement('i');
  if (string.toLowerCase() == 'pass') {
    itag.className = 'fas fa-check';
    rowEl.children[col].innerHTML = null;
    rowEl.children[col].appendChild(itag);
  } else if (string.toLowerCase() == 'fail') {
    itag.className = 'fas fa-times';
    rowEl.children[col].innerHTML = null;
    rowEl.children[col].appendChild(itag);
  } else {
    console.log('pass/fail not in column' + col)
  }
  return rowEl;
}

function linkifyFromArray(tag, linkArray) {
  // console.log('function linkifyFromArray(tag, linkArray)')
  if (Object.prototype.toString.call(linkArray) == '[object String]') {
    return linkifyFromString(tag, linkArray);
  }
  var linkText = '';
  for (link of linkArray) {
    linkText = linkText + link + '<br>'; // Append link
  }

  return linkifyFromString(tag, linkText.substr(0, linkText.length-4)); // Remove last <br>
}

function linkifyFromString(tag, htmlText) {
  // console.log('function linkifyFromString(tag, htmlText)')
  tag.innerHTML = null;
  tag.innerHTML = htmlText;
  let anchors = tag.getElementsByTagName('a')
  if (anchors.length > 0) {
    for (let a of anchors) {
      a.className = 'stmt-dblink'
      a.target = "_blank"
    }
  }
  // console.log(tag)
  return tag;
}

function addLineBreaks(rowEl, col) {
  // Adds <br> after '.' to text in specified column
  let breakText = rowEl.children[col].textContent.replace(/\./g, '.<br>')
  rowEl.children[col].innerHTML = null;
  rowEl.children[col].innerHTML = breakText.substr(0, breakText.length-4); // Remove last <br>
  return rowEl;
}

function populateModelsTable(metaTableBody, json) {
  // console.log('function populateModelsTable(metaTableBody, json)')
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
      link.target = '_blank'
    } else {
      link.textContent = 'No evidence'
    }

    let tableRow = addToRow(plainEnglish, '')
    tableRow.children[1].innerHTML = null;
    tableRow.children[1].appendChild(link)

    metaTableBody.appendChild(tableRow);
  }
}

function getTestResultJsonToTable(testResultTableBody, jsonKey) {
  // console.log('function getTestResultJsonToTable(testResultTableBody, jsonKey)');
  let jsonPromise = getPublicJson(EMMMAA_BUCKET, jsonKey);
  jsonPromise.then(function(json){
    populateTestResultTable(testResultTableBody, json);
  })
}

// Populate test results json to modelTestResultBody
function populateTestResultTable(tableBody, json) {
  console.log('function populateTestResultTable(tableBody, json)');
  // console.log(tableBody)
  console.log('test results json');
  console.log(json);

  // IDs
  let stmtTypDistId = '#modelTestResultBody'
  let pasRatId = '#passedRatio'
  let pasAppId = '#passedApplied'
  let agDist = '#agentDistr'
  let stmtTime = '#stmtsOverTime'

  // Dates
  dates = json.changes_over_time.dates
  dates.unshift('x')

  //  Model Tab

  // Stmt type distribution bar graph 
  var stmt_type_array = []
  var stmt_freq_array = ['count']

  for (pair of json.model_summary.stmts_type_distr) {
    stmt_type_array.push(pair[0])
    stmt_freq_array.push(pair[1])
  }
  // See example at: https://c3js.org/samples/axes_x_tick_format.html
  // console.log('stmt_type_array: ' + stmt_type_array)
  // console.log('stmt_freq_array: ' + stmt_freq_array)
  stmtTypeDataParams = {
    // x: 'x',
    columns: [
      stmt_freq_array
    ],
    type: 'bar'
  }

  var stmtTypeChart = generateBar(stmtTypDistId, stmtTypeDataParams, stmt_type_array, '')

  // Top agents bar graph
  var top_agents_array = []
  var agent_freq_array = ['count']

  for (pair of json.model_summary.agent_distr.slice(0, 10)) {
    top_agents_array.push(pair[0])
    agent_freq_array.push(pair[1])
  }

  agentDataParams = {
    columns: [
      agent_freq_array
    ],
    type: 'bar'
  }

  var agentChart = generateBar(agDist, agentDataParams, top_agents_array, '')

  // Statements by Evidence Table
  let stEvTable = document.getElementById('stmtEvidence')
  clearTable(stEvTable)
  var english_stmts = json.model_summary.english_stmts
  var stmtByEv = json.model_summary.stmts_by_evidence

  for (pair of stmtByEv.slice(0,10)) {
    let rowEl = addToRow(['', pair[1]])
    rowEl.children[0] = linkifyFromString(rowEl.children[0], english_stmts[pair[0]]);
    stEvTable.appendChild(rowEl)
  }

  // Statements over Time line graph
  stmtsOverTime = json.changes_over_time.number_of_statements
  stmtsOverTime.unshift('Statements')

  stmtsCountDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      dates,
      stmtsOverTime
    ]
  }

  var stmtsCountChart = generateLineArea(stmtTime, stmtsCountDataParams, '')

  // Model Delta - New statements
  let newStTable = document.getElementById('addedStmts')
  clearTable(newStTable)
  var new_stmts = json.model_delta.statements_delta.added
  // console.log(new_stmts)
  for (stmt of new_stmts) {
    // Has columns: statements
    let rowEl = addToRow([stmt])
    rowEl.children[0] = linkifyFromString(rowEl.children[0], stmt)
    newStTable.appendChild(rowEl)
  }
  // Tests Tab

  // Passed ratio line graph
  passedRatio = json.changes_over_time.passed_ratio
  passedRatio = passedRatio.map(function(element) {
    return (element*100).toFixed(2);
  })
  // console.log('ratio %' + passedRatio)
  passedRatio.unshift('Passed Ratio')

  lineDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      dates,
      passedRatio
    ]
  }

  var lineChart = generateLineArea(pasRatId, lineDataParams, '');

  // Applied/passed area graph
  appliedTests = json.changes_over_time.number_applied_tests
  appliedTests.unshift('Applied Tests')
  passedTests = json.changes_over_time.number_passed_tests
  passedTests.unshift('Passed Tests')

  passedAppliedParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      dates,
      passedTests,
      appliedTests
    ],
    type: 'area'
  }

  var areaChart = generateLineArea(pasAppId, passedAppliedParams, '');

  // Tests Delta - New Applied Tests
  let newAppliedTable = document.getElementById('newAppliedTests')
  clearTable(newAppliedTable)
  var newAppTests = json.tests_delta.applied_tests_delta.added

  for (pair of newAppTests) {
    // Has columns: Test; Status;
    let rowEl = addToRow(pair)
    rowEl = generatePassFail(rowEl, 1)
    rowEl.children[0] = linkifyFromString(rowEl.children[0], pair[0])
    newAppliedTable.appendChild(rowEl)
  }
  // Tests Delta - New Passed Tests
  let newPassedTable = document.getElementById('newPassedTests')
  clearTable(newPassedTable)
  var newPasTests = json.tests_delta.pass_fail_delta.added
  var newPaths = json.tests_delta.new_paths.added

  for (i = 0; i < newPasTests.length; i++) {
    // Has columns: test; Path Found
    // let rowEl = addToRow([newPasTests[i], newPaths[i]])
    let rowEl = addToRow(['', ''])
    rowEl.children[0] = linkifyFromString(rowEl.children[0], newPasTests[i])
    rowEl.children[1] = linkifyFromArray(rowEl.children[1], newPaths[i][0])
    newPassedTable.appendChild(rowEl)
  }

  // All Tests Results
  let allTestsTable = document.getElementById('allTestResults')
  clearTable(allTestsTable)
  var testResults = json.test_round_summary.tests_by_hash
  var resultValues = Object.values(testResults)
  resultValues.sort(function(a,b){return (a[1] < b[1]) ? 1 : (a[1] > b[1]) ? -1 : 0;});

  for (val of resultValues) {
    // Has columns: test; Status; Path Found;
    let rowEl = addToRow(val)
    rowEl.children[0] = linkifyFromString(rowEl.children[0], val[0])
    rowEl.children[2] = linkifyFromArray(rowEl.children[2], val[2][0])
    allTestsTable.appendChild(generatePassFail(rowEl, 1))
  }

  // Force redraw of charts to prevent chart overflow
  // https://c3js.org/reference.html#api-flush
  $('a[data-toggle=tab]').on('shown.bs.tab', function() { // This will trigger when tab is clicked
    stmtTypeChart.flush();
    agentChart.flush();
    stmtsCountChart.flush();
    lineChart.flush();
    areaChart.flush();
  });
}

function listModelInfo(modelInfoTableBody, lastUpdated, ndexID) {
  // 1. Last updated: get from listing models using already created function
  // 2. NDEX link-out: read from config
  // 3. Possibly listing nodes and edges info (Q: from where? A: From the json files that don't exist yet)

  // Add when model was last updated
  modelInfoTableBody.appendChild(addToRow(['Last updated', lastUpdated]))
  // Create link to ndex
  let link = document.createElement('a');
  link.textContent = ndexID;
  link.href = 'http://www.ndexbio.org/#/network/' + ndexID;
  link.target = '_blank';

  tableRow = addToRow(['Network on NDEX', '']);
  tableRow.children[1].innerHTML = null;
  tableRow.children[1].appendChild(link);

  modelInfoTableBody.appendChild(tableRow);
}

function modelsLastUpdated(keyMapArray, endsWith) {
  //  for each model:
  //    get list of all pickles
  //    sort list descending, alphabetical, order
  //    get first (i.e. latest) item
  //    item.split('/')[2].split('_')[1].split('.')[0] gives datetime string
  // console.log('Objects in bucket: ')
  // console.log(keyMapArray)
  let modelsMapArray = getModels(null, keyMapArray, endsWith)
  // console.log('Following objects mapped to models, filtered for object keys ending in ' + endsWith)
  // console.log(modelsMapArray)

  let modelUpdateTagsArray = document.getElementsByClassName('modelUpdateInfo')
  for (tag of modelUpdateTagsArray) {
    let model = tag.getAttribute('id').split('Update')[0]
    if (model) {
      lastUpdated = modelsMapArray[model].sort()[modelsMapArray[model].length - 1].split('.')[0].split('_')[1]
      tag.textContent = 'Last updated: ' + lastUpdated;
    }
  }
}

function getModels(findModel, keyMapArray, endsWith) {
  // console.log('function getModels(findModel, keyMapArray, endsWith)')
  var models = {}
  for (m of MODELS_ARRAY) {
    models[m] = []
  }
  for (keyItem of keyMapArray) {
    if (keyItem.Key.endsWith(endsWith) & keyItem.Key.split('/').length == 3) {
      let model = keyItem.Key.split('/')[1]
      if (!findModel) {
        // Save all models
        if (model) {
          models[model].push(keyItem.Key.split('/')[2])
        } else console.log('Unhandled model ' + model)
      } else {
        // Save just the model we're interested in
        if (findModel && findModel == model) {
          models[model].push(keyItem.Key.split('/')[2])
        }
      }
    }
  }
  return models;
}

function listModelTests(tableBody, testResultTableBody, keyMapArray, model, endsWith) {
  // console.log('function listModelTests(tableBody, testResultTableBody, keyMapArray, model, endsWith)')
  
  // get array of filtered object keys
  let testJsonsArray = getArrayOfModelTests(model, keyMapArray, endsWith);
  let sortedTestJsonsArray = testJsonsArray.sort();

  getTestResultJsonToTable(testResultTableBody, sortedTestJsonsArray[sortedTestJsonsArray.length-1]);
  
  // // loop the sorted array in reverse alphbetical order (newest first)
  // for (let i = sortedTestJsonsArray.length-1; i >= 0; i--) {
  //   var testString = ''
  //   if (sortedTestJsonsArray[i].split('/')[2].includes('_')) {
  //     testString = sortedTestJsonsArray[i].split('/')[2].split('.')[0].split('_')[1];
  //   } else {
  //     testString = sortedTestJsonsArray[i].split('/')[2].split('.')[0];
  //   }
  //   link = document.createElement('a');
  //   link.textContent = testString;
  //   link.href = '#Test Result Details'
  //   link.value = sortedTestJsonsArray[i]
  //   link.onclick = function() { // Attach function call to link
  //     getTestResultJsonToTable(testResultTableBody, this.value);
  //   }

  //   let tableRow = addToRow(model, '');
  //   tableRow.children[1].innerHTML = null;
  //   tableRow.children[1].appendChild(link);

  //   tableBody.appendChild(tableRow);
  // }
}

function getArrayOfModelTests(model, keyMapArray, endsWith) {
  // console.log('function getArrayOfModelTests(model, keyMapArray, endsWith)');
  //  for each object ket
  //    if key.endswith(endsWith) & correct prefix
  //      save to list
  var tests = [];
  for (object of keyMapArray) {
    if (object.Key.endsWith(endsWith) & object.Key.split('/')[1] == model & object.Key.split('/').length == 3) {
      tests.push(object.Key);
    }
  }
  // if (tests.length > 0) {
  //   console.log('Non-zero array of test jsons resolved')
  //   console.log(tests)
  // }
  return tests;
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

/* c3 chart functions
Found here:

https://c3js.org/
*/

function generateBar(chartDivId, dataParams, ticksLabels, chartTitle) {
  // console.log('function generateBar(chartDivId, dataParams)')
  // console.log(chartDivId)
  // console.log(dataParams)
  var barChart = c3.generate({
    bindto: chartDivId,
    data: dataParams,
    bar:  {
      width: {
        ratio: 0.5 // this makes bar width 50% of length between ticks
      }
    },
    axis: {
      rotated: true,
      x: {
          type: 'category',
          categories: ticksLabels
      }
    },
    title: {
      text: chartTitle
    }
  });
  return barChart;
}

function generateLineArea(chartDivId, dataParams, chartTitle) {
  // console.log('function generateLine(chartId, dataparams)')
  // console.log(chartDivId)
  // console.log(dataParams)
  var lineChart = c3.generate({
    bindto: chartDivId,
    data: dataParams,
    axis: {
      x: {
        type: 'timeseries',
        tick: {
          rotate: -45,
          format: '%Y-%m-%d-%H-%M-%S'
        }
      }
    },
    title: {
      text: chartTitle
    },
    zoom: {
      enabled: true
    }
  });
  return lineChart;
}

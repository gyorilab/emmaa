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
  console.log('function selectModel(modelInfoTableBody, listTestResultsTableBody, testResultTableBody, ddSelect)')
  // Get selected option
  var model = '';
  for (child of ddSelect.children) {
    if (child.selected) {
      model = child.value;
      break;
    }
  }

  if (model == 'brca') {
    alert('BRCA Model Currently Unavailable')
    return;
  }

  endsWith = '.json';
  maxKeys = 1000;  resultsPrefix = 'stats';
  modelsPrefix = 'models';
  let s3Interface = new AWS.S3();

  // List model info
  loadModelMetaData(modelInfoTableBody, EMMMAA_BUCKET, model, maxKeys, modelsPrefix, '.pkl')

  // Pass tables, model and mode to function that lists the latest tests
  listObjectsInBucketUnAuthenticated('listModelTests', listTestResultsTableBody, testResultTableBody, s3Interface, EMMMAA_BUCKET, model, resultsPrefix, maxKeys, endsWith)
}

function loadModelMetaData(modelInfoTable, bucket, model, maxKeys, prefix, endsWith) {
  console.log('function loadModelMetaData(modelInfoTable, bucket, model, maxKeys, prefix, endsWith)')
  // wrapper function that can be called selectModel or from pageload of models.html
  // mode, tableBody, testResultTableBody, s3Interface, bucket, model, prefix, maxKeys, endsWith
  listObjectsInBucketUnAuthenticated('listModelInfo', modelInfoTable, null, new AWS.S3(), bucket, model, prefix, maxKeys, endsWith)
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

function getTestResultJsonToTable(testResultTableBody, jsonKey) {
  console.log('function getTestResultJsonToTable(testResultTableBody, jsonKey)');
  let jsonPromise = getPublicJson(EMMMAA_BUCKET, jsonKey);
  jsonPromise.then(function(json){
    populateTestResultTable(testResultTableBody, json);
  })
}

// Populate test results json to modelTestResultBody
function populateTestResultTable(tableBody, json) {
  console.log('function populateTestResultTable(tableBody, json)')
  console.log(tableBody)
  console.log(json)

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
  console.log('stmt_type_array: ' + stmt_type_array)
  console.log('stmt_freq_array: ' + stmt_freq_array)
  stmtTypeDataParams = {
    // x: 'x',
    columns: [
      stmt_freq_array
    ],
    type: 'bar'
  }

  let stmtTypeChart = generateBar(stmtTypDistId, stmtTypeDataParams, stmt_type_array, '')

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

  let agentChart = generateBar(agDist, agentDataParams, top_agents_array, '')

  // Statements by Evidence Table
  let stEvTable = document.getElementById('stmtEvidence')
  clearTable(stEvTable)
  var english_stmts = json.model_summary.english_stmts
  var stmtByEv = json.model_summary.stmts_by_evidence

  for (pair of stmtByEv.slice(0,10)) {
    let rowEl = addToRow(english_stmts[pair[0]], pair[1])
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

  let stmtsCountChart = generateLineArea(stmtTime, stmtsCountDataParams, '')

  // Model Delta - New statements
  let newStTable = document.getElementById('addedStmts')
  clearTable(newStTable)
  var new_stmts = json.model_delta.statements_delta.added
  console.log(new_stmts)
  for (stmt of new_stmts) {
    let rowEl = addToRow(stmt, '')
    newStTable.appendChild(rowEl)
  }
  // Tests Tab

  // Passed ratio line graph
  passedRatio = json.changes_over_time.passed_ratio
  passedRatio = passedRatio.map(function(element) {
    return (element*100).toFixed(2);
  })
  console.log('ratio %' + passedRatio)
  passedRatio.unshift('Passed Ratio')

  lineDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      dates,
      passedRatio
    ]
  }

  let lineChart = generateLineArea(pasRatId, lineDataParams, '')
  console.log(lineChart)

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

  let areaChart = generateLineArea(pasAppId, passedAppliedParams, '')

  // Tests Delta - New Applied Tests
  let newAppliedTable = document.getElementById('newAppliedTests')
  clearTable(newAppliedTable)
  var newAppTests = json.tests_delta.applied_tests_delta.added

  for (test of newAppTests) {
    let rowEl = addToRow(test, '')
    newAppliedTable.appendChild(rowEl)
  }
  // Tests De;ta - New Passeed Tests
  let newPassedTable = document.getElementById('newPassedTests')
  clearTable(newPassedTable)
  var newPasTests = json.tests_delta.passed_tests_delta.added
  var newPaths = json.tests_delta.new_paths.added

  for (i = 0; i < newPasTests.length; i++) {
    let rowEl = addToRow(newPasTests[i], newPaths[i])
    newAppliedTable.appendChild(rowEl)
  }
}

function listModelInfo(modelInfoTableBody, keyMapArray, bucket, model, endsWith) {
  console.log('listModelInfo(modelInfoTableBody, keyMapArray, bucket, model, endsWith)')
  // 1. Last updated: get from listing models using already created function
  // 2. NDEX link-out: read yaml as plain text and reg-exp match your way to the NDEX if
  // 3. Possibly listing nodes and edges info (Q: from where? A: From the json files that don't exist yet)

  // Get an array of the models for model
  modelsMapArray = getModels(model, keyMapArray, endsWith)
  // console.log('modelsMapArray')
  // console.log(modelsMapArray)
  clearTable(modelInfoTableBody)
  var lastUpdated = ''
  if (modelsMapArray[model].sort()[modelsMapArray[model].length - 1].includes('_')) {
    lastUpdated = modelsMapArray[model].sort()[modelsMapArray[model].length - 1].split('.')[0].split('_')[1]
  } else {
    lastUpdated = modelsMapArray[model].sort()[modelsMapArray[model].length - 1].split('.')[0]
  }
  modelInfoTableBody.appendChild(addToRow('Last updated', lastUpdated))

  // Get NDEX id from YAML
  // let yamlKey = 'models/' + model + '/config.yaml';
  // console.log('yamlPromise')
  // console.log(yamlPromise)
  // yamlPromise.then(function(jsonText){
  //   console.log('Resovled YAML file as:')
  //   console.log(jsonText)
  //   console.log('reg-exp match')
  //   console.log(jsonText.match(/ndex\: \{network\: ([a-z0-9\-]+)\}/)[1]);

  //   let ndexID = jsonText.match(/ndex\: \{network\: ([a-z0-9\-]+)\}/)[1];
    
  //   let link = document.createElement('a')
  //   link.textContent = ndexID;
  //   link.href = 'http://www.ndexbio.org/#/network/' + ndexID;
    
  //   tableRow = addToRow('Network on NDEX', '')
  //   tableRow[1].innerHTML = null;
  //   tableRow[1].appendChild(link)
    
  //   modelInfoTableBody.appendChild(tableRow)
  // })

  console.log('Hello')
  var yamlURL = 'https://s3.amazonaws.com/' + bucket + '/models/' + model + '/config.yaml';
  var yamlPromise = $.ajax({
    url: yamlURL,
    dataType: "text",
    success: function(response) {
      // console.log(response)
      // console.log(response.match(/ndex\: \{network\: ([a-z0-9\-]+)\}/)[1]);
      let ndexID = response.match(/ndex\: \{network\: ([a-z0-9\-]+)\}/)[1];
      let link = document.createElement('a');
      link.textContent = ndexID;
      link.href = 'http://www.ndexbio.org/#/network/' + ndexID;
      
      tableRow = addToRow('Network on NDEX', '');
      tableRow.children[1].innerHTML = null;
      tableRow.children[1].appendChild(link);
      
      modelInfoTableBody.appendChild(tableRow);
      }
  });

  // List info from json of model
  // modelMetaInfoPromise = getPublicJson(bucket, modelKey)
  // modelMetaInfoPromise.then(function(json) {
  //   populateModelsTable(modelInfoTable, json);
  // });
}

function modelsLastUpdated(keyMapArray, endsWith) {
  //  for each model:
  //    get list of all pickles
  //    sort list descending, alphabetical, order
  //    get first (i.e. latest) item
  //    item.split('/')[2].split('_')[1].split('.')[0] gives datetime string
  console.log('Objects in bucket: ')
  console.log(keyMapArray)
  let modelsMapArray = getModels(null, keyMapArray, endsWith)
  console.log('Following objects mapped to models, filtered for object keys ending in ' + endsWith)
  console.log(modelsMapArray)

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
  console.log('function getModels(findModel, keyMapArray, endsWith)')
  var models = {'aml': [],
                'brca': [],
                'luad': [],
                'paad': [],
                'prad': [],
                'skcm': [],
                'rasmodel': [],
                'test': []}
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
  console.log('function listModelTests(tableBody, testResultTableBody, keyMapArray, model, endsWith)')
  
  // get array of filtered object keys
  let testJsonsArray = getArrayOfModelTests(model, keyMapArray, endsWith)
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
  console.log('function getArrayOfModelTests(model, keyMapArray, endsWith)');
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
  console.log('function generateBar(chartDivId, dataParams)')
  console.log(chartDivId)
  console.log(dataParams)
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
  console.log('function generateLine(chartId, dataparams)')
  console.log(chartDivId)
  console.log(dataParams)
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
    }
  });
}
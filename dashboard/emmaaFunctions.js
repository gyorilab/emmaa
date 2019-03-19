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

function listModelInfo(modelInfoTableBody, keyMapArray, bucket, model, endsWith) {
  console.log('listModelInfo(modelInfoTableBody, keyMapArray, bucket, model, endsWith)')
  // 1. Last updated: get from listing models using already created function
  // 2. NDEX link-out: read yaml as plain text and reg-exp match your way to the NDEX if
  // 3. Possibly listing nodes and edges info (Q: from where? A: From the json files that don't exist yet)

  // Get an array of the models for model
  modelsMapArray = getModels(model, keyMapArray, endsWith)
  // console.log('modelsMapArray')
  // console.log(modelsMapArray)
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
  
  // loop the sorted array in reverse alphbetical order (newest first)
  for (let i = sortedTestJsonsArray.length-1; i >= 0; i--) {
    var testString = ''
    if (sortedTestJsonsArray[i].split('/')[2].includes('_')) {
      testString = sortedTestJsonsArray[i].split('/')[2].split('.')[0].split('_')[1];
    } else {
      testString = sortedTestJsonsArray[i].split('/')[2].split('.')[0];
    }
    link = document.createElement('a');
    link.textContent = testString;
    link.href = '#Test Result Details'
    link.value = sortedTestJsonsArray[i]
    link.onclick = function() { // Attach function call to link
      getTestResultJsonToTable(testResultTableBody, this.value);
    }

    let tableRow = addToRow(model, '');
    tableRow.children[1].innerHTML = null;
    tableRow.children[1].appendChild(link);

    tableBody.appendChild(tableRow);
  }
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

function generateBar(chartDivId, dataParams, ticksLabels) {
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
        tick: {
          ticksLabels
        }
      }
    }
  });
  return barChart;
}

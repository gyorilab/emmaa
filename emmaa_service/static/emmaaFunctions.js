/* emmaaFunctions.js - main javascript functions for the ASKE emmaa project

This file contains helper functions and project specific functions that does 
the client side work of exposing cancer network models for the end users

*/

// CONSTANTS AND IDs
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
  tag.innerHTML = null;
  tag.innerHTML = htmlText;
  let anchors = tag.getElementsByTagName('a')
  if (anchors.length > 0) {
    for (let a of anchors) {
      a.className = 'stmt-dblink'
      a.target = "_blank"
    }
  }
  return tag;
}

// Populate test results json to modelTestResultBody
function populateTestResultTable(tableBody, json) {

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

/* c3 chart functions
Found here:

https://c3js.org/
*/

function generateBar(chartDivId, dataParams, ticksLabels, chartTitle) {
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

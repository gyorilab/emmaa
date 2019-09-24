/* emmaaFunctions.js - main javascript functions for the ASKE emmaa project

This file contains helper functions and project specific functions that does 
the client side work of exposing cancer network models for the end users

*/

function setModel(ddSelect, model) {
  // Sets the selected option
  // let ddSelect = document.getElementById('modelSelectDD');
  for (child of ddSelect.children) {
    if (model === child.value) {
      child.selected = 'selected';
      break;
    }
  }
}

function clearTables(arrayOfTableBodies) {
  for (let tableBody of arrayOfTableBodies) {
    clearTable(tableBody)
  }
}

function clearTable(tableBody) {
  tableBody.innerHTML = null;
}

// Creates a new table row given an array of values
function addToRow(col_values) {
  let tableRow = document.createElement('tr');

  for (let col of col_values) {
    let column = document.createElement('td');
    column.textContent = col;
    tableRow.appendChild(column);
  }

  return tableRow;
}

// Creates a new table row by merging the columns
function addMergedRow(value, num_cols) {
  let tableRow = document.createElement('tr');
  let column = document.createElement('td')
  column.colSpan = num_cols
  column.innerHTML = value.bold()
  column.style.textAlign = "center"
  tableRow.appendChild(column);
  return tableRow;
}

function generatePassFail(rowEl, cols) {
  // See more at:
  // https://fontawesome.com/icons?d=gallery
  // Pass: <i class="fas fa-check"></i>
  // Fail: <i class="fas fa-times"></i>
  for (col of cols) {
    let string = rowEl.children[col].textContent;
    let itag = document.createElement('i');
    if (string.toLowerCase() === 'pass') {
      itag.className = 'fas fa-check';
      rowEl.children[col].innerHTML = null;
      rowEl.children[col].style.textAlign = "center"
      rowEl.children[col].appendChild(itag);
    } else if (string.toLowerCase() === 'fail') {
      itag.className = 'fas fa-times';
      rowEl.children[col].innerHTML = null;
      rowEl.children[col].style.textAlign = "center"
      rowEl.children[col].appendChild(itag);
    } else {
      console.log(`pass/fail not in column ${col}`)
    }
  }
  return rowEl;
}

function linkifyFromArray(tag, linkArray) {
  if (Object.prototype.toString.call(linkArray) === '[object String]') {
    return linkifyFromString(tag, linkArray);
  }
  let linkText = '';
  for (link of linkArray) {
    linkText = `${linkText}${link}<br>`; // Append link
  }

  return linkifyFromString(tag, linkText.substr(0, linkText.length-4)); // Remove last <br>
}

function linkifyFromString(tag, htmlText) {
  tag.innerHTML = null;
  tag.innerHTML = htmlText;
  let anchors = tag.getElementsByTagName('a');
  if (anchors.length > 0) {
    for (let a of anchors) {
      a.className = 'stmt-dblink';
      a.target = "_blank"
    }
  }
  return tag;
}

function countPasses(results, mts) {
  let count = 0;
  for (mt of mts) {
    if (results[mt][0].toLowerCase() === 'pass') {count++};
  }
  return count;
};

function toTitleCase(phrase) {
  let newPhrase = phrase.split('_');
  newPhrase = newPhrase.map(word => word.charAt(0).toUpperCase() + word.slice(1));
  newPhrase = newPhrase.join(' ');
  return newPhrase;
};

// Populate test results json to modelTestResultBody
function populateTestResultTable(tableBody, json) {

  // IDs
  let stmtTypDistId = '#modelTestResultBody';
  let pasRatId = '#passedRatio';
  let pasAppId = '#passedApplied';
  let agDist = '#agentDistr';
  let stmtTime = '#stmtsOverTime';

  // Dates
  dates = json.changes_over_time.dates;
  dates.unshift('x');

  let all_model_types = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
  let current_model_types = [];
  let cols = [];
  let count = 0;
  for (mt of all_model_types) {if (mt in json.test_round_summary) {
    current_model_types.push(mt)
    count++
    cols.push(count)}};

  //  Model Tab

  // Stmt type distribution bar graph 
  let stmt_type_array = [];
  let stmt_freq_array = ['count'];

  for (let pair of json.model_summary.stmts_type_distr) {
    stmt_type_array.push(pair[0]);
    stmt_freq_array.push(pair[1])
  }
  // See example at: https://c3js.org/samples/axes_x_tick_format.html
  stmtTypeDataParams = {
    // x: 'x',
    columns: [
      stmt_freq_array
    ],
    type: 'bar'
  };

  let stmtTypeChart = generateBar(stmtTypDistId, stmtTypeDataParams, stmt_type_array, '');

  // Top agents bar graph
  let top_agents_array = [];
  let agent_freq_array = ['count'];

  for (let pair of json.model_summary.agent_distr.slice(0, 10)) {
    top_agents_array.push(pair[0]);
    agent_freq_array.push(pair[1])
  }

  let agentDataParams = {
    columns: [
      agent_freq_array
    ],
    type: 'bar'
  };

  let agentChart = generateBar(agDist, agentDataParams, top_agents_array, '');

  // Statements over Time line graph
  let stmtsOverTime = json.changes_over_time.number_of_statements;
  stmtsOverTime.unshift('Statements');

  let stmtsCountDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      dates,
      stmtsOverTime
    ]
  };

  let stmtsCountChart = generateLineArea(stmtTime, stmtsCountDataParams, '');

  // Tests Tab

  // Passed ratio line graph
  let passedRatioColumns = [dates]

  for (mt of current_model_types) {
    let mt_changes = json.changes_over_time[mt]
    let passedRatio = mt_changes.passed_ratio
    passedRatio = passedRatio.map(function(element) {
      return (element*100).toFixed(2);
    })
    var i
    let dif = dates.length - passedRatio.length
    for (i = 1; i < dif; i++) {passedRatio.unshift(null)}
    passedRatio.unshift(toTitleCase(mt))
    passedRatioColumns.push(passedRatio)
  };

  lineDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: passedRatioColumns
  };

  let lineChart = generateLineArea(pasRatId, lineDataParams, '');

  // Applied/passed area graph
  let appliedTests = json.changes_over_time.number_applied_tests;
  appliedTests.unshift('Applied Tests');
  let appliedPassedColumns = [dates, appliedTests]

  for (mt of current_model_types) {
    let mt_changes = json.changes_over_time[mt]
    let passedTests = mt_changes.number_passed_tests;
    var i
    let dif = dates.length - passedTests.length
    for (i = 1; i < dif; i++) {passedTests.unshift(null)}
    passedTests.unshift(`${toTitleCase(mt)} Passed Tests`)
    appliedPassedColumns.push(passedTests)
  };

  let passedAppliedParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: appliedPassedColumns,
    type: 'area'
  };

  let areaChart = generateLineArea(pasAppId, passedAppliedParams, '');

  // Retrieve all test results for the next tables
  let allTestResults = json.test_round_summary.all_test_results;

  // Tests Delta - New Passed Tests
  let newPassedTable = document.getElementById('newPassedTests');
  clearTable(newPassedTable);
  for (mt of current_model_types) {
    let newPasHashes = json.tests_delta[mt].passed_hashes_delta.added;
    if (newPasHashes && newPasHashes.length > 0) {
      newRow = addMergedRow(`New passed tests for ${toTitleCase(mt)} model.`, 2);
      newPassedTable.appendChild(newRow);
      for (testHash of newPasHashes) {
        let rowEl = addToRow(['', '']);
        rowEl.children[0] = linkifyFromString(
          rowEl.children[0], allTestResults[testHash]["test"]);
        rowEl.children[1] = linkifyFromArray(
          rowEl.children[1], allTestResults[testHash][mt][1][0]);
          newPassedTable.appendChild(rowEl);};
    };
  };

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

/* c3 chart functions
Found here:

https://c3js.org/
*/

function generateBar(chartDivId, dataParams, ticksLabels, chartTitle) {
  return c3.generate({
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
}

function generateLineArea(chartDivId, dataParams, chartTitle) {
  return c3.generate({
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
}

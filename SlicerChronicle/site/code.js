var studies;
var table;
$(function(){ // on dom ready


  var chURLPrefix = "http://common.bwh.harvard.edu:5984";
  var chDatabase = "chronicle";

  var chronicle = new PouchDB(chURLPrefix+'/'+chDatabase);

  // http://www.datatables.net/examples/api/multi_filter.html
  var addColumnSearch = function (tableID) {
    // add search boxes per column
    $(tableID+' tfoot th').each( function() {
      var title = $(tableID+' thead th').eq( $(this).index() ).text();
      $(this).html( '<input type="text" placeholder="Search '+title+'" />' );
    });
    var dataTable = $(tableID).DataTable();
    // apply the search
    dataTable.columns().eq(0).each(function(columnIndex) {
      $('input', dataTable.column(columnIndex).footer()).on('keyup change', function() {
        dataTable
          .column(columnIndex)
          .search(this.value)
          .draw();
      })
    });
  };

  // Series
  studyDataTable = $('#studyDataTable').DataTable();
  chronicle.query("instances/context", {
    reduce : true,
    group_level : 2,
    //limit: 5,
  }).then(function(data) {
    // add table entries for each hit
    $.each(data.rows, function(index,row) {
      var institution = row.key[0][0];
      var patientUID = String(row.key[0]);
      var patientID = row.key[0][1];
      var studyDescription = row.key[1][0];
      var studyUID = row.key[1][1];
      var seriesCount = row.value;
      studyDataTable.row.add(['', patientID, studyDescription]).draw();
    });
    addColumnSearch('#studyDataTable');
  });



  // Instance
  instanceDataTable = $('#instanceDataTable').DataTable();

  var i;
  for (i = 0; i < 11000; i++) {
    instanceDataTable.row.add(['test', String(i)]);
  }
  instanceDataTable.draw();
  addColumnSearch('#instanceDataTable');
  return;

  chronicle.query("instances/context", {
    reduce : true,
    group_level : 4,
    limit : 1000,
  }).then(function(data) {
    // add table entries for each hit
    $.each(data.rows, function(index,row) {
      var modality = row.key[2][0];
      var instanceUID = row.key[3];
      //instanceDataTable.row.add([modality, instanceUID]);
    });
    instanceDataTable.draw();
  });

  $('#studyDataTable tbody').on('click', 'tr', function() {
    console.log($(this));
  });

  return;

}); // on dom ready

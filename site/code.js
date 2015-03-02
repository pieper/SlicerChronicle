var studies;
var table;
$(function(){ // on dom ready


  $.couch.urlPrefix = "http://common.bwh.harvard.edu:5984";

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
  $.couch.db("chronicle").view("instances/context", {
    reduce : true,
    group_level : 2,
    //limit: 5,
    success: function(data) {
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
    }
  });



  // Instance
  instanceDataTable = $('#instanceDataTable').DataTable();

  var i;
  for (i = 0; i < 1100; i++) {
    instanceDataTable.row.add(['test', String(i)]);
  }
  instanceDataTable.draw();
  addColumnSearch('#instanceDataTable');
  return;

  $.couch.db("chronicle").view("instances/context", {
    reduce : true,
    group_level : 4,
    limit : 1000,
    success: function(data) {
      // add table entries for each hit
      $.each(data.rows, function(index,row) {
        var modality = row.key[2][0];
        var instanceUID = row.key[3];
        //instanceDataTable.row.add([modality, instanceUID]);
      });
      instanceDataTable.draw();
    }
  });

  $('#studyDataTable tbody').on('click', 'tr', function() {
    console.log($(this));
  });

  return;

function fetchStudyEdge(id) {
  $.couch.db("chronicle").openDoc(id, {
    success : function(data) {
      var noDotsID = id.replace(/\./g, '_');
      studyUID = data.dataset['0020000D'].Value;
      var noDotsStudyID = studyUID.replace(/\./g, '_');
      cy.add({
        group : "edges",
        data : { id : noDotsID+'_to_'+noDotsStudyID, source : noDotsID, target : noDotsStudyID},
      });

      console.log(data.dataset['0020000D']);
    },
    error : function(status) {
      console.log(status);
    }
  });
};

var value = "Slicer Study Render";
$.couch.db("chronicle").view("tags/byTagAndValue", {
  startkey: ["0008103E", value],
  endkey: ["0008103E", value+"\u9999"],
  reduce : false,
  stale : 'update_after',
  //limit : 30,
  success: function(data) {
    $.each(data.rows, function(index,row) {
      var id = row.id;
      var imageURL = 'http://common.bwh.harvard.edu:5984/chronicle/' + id + '/image.jpg';
      var group = "nodes";
      var noDotsID = id.replace(/\./g, '_');
      var cyID = '#' + noDotsID;
      cy.add({
          group: group,
          data: { id: noDotsID, weight: 75 },
          position: { x: 200, y: 200 }
      });
      cy.$(cyID).css('shape', 'rectangle');
      /*
      cy.$(cyID).css('background-image', imageURL);
      cy.$(cyID).css('width', '1200px');
      cy.$(cyID).css('height', '1200px');
      */
      fetchStudyEdge(id);
    });
    cy.layout({name: "grid"});
  },
});

}); // on dom ready

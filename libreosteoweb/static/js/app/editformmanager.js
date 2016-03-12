var editFormManager = angular.module('loEditFormManager', []);

var MutationObserver = window.MutationObserver || window.WebKitMutationObserver || window.MozMutationObserver;


function Callback(name, callback) {
  this.name = name;
  this.callback = callback;
}

editFormManager.factory('loEditFormManager', function() {
  var forms = [];
  var actions = ['edit', 'cancel', 'save', 'delete'];
  var callback_form = [];
  var triggers_form = [];
  return {
    add: function(form, action_list, trigger) {
      if (forms.indexOf(form) === -1) {
        forms.push(form);
      }
      angular.forEach(action_list, function(action, key) {
        if (action && actions.indexOf(action.name) != -1) {
          var idx_form = forms.indexOf(form);
          var should_add = true;
          var callbacks = null;
          angular.forEach(callback_form, function(value, key) {
            if (value.id == idx_form) {
              should_add = false;
              callbacks = value.callbacks;
            }
          });
          if (should_add) {
            callback_form.push({
              id: forms.indexOf(form),
              callbacks: [action]
            });
          } else {
            callbacks.push(action);
          }
        }
      });
      var idx_form = forms.indexOf(form);
      if (trigger) 
        triggers_form[idx_form] = trigger;
    },
    isavailable: function() {
      this.available = this._visibleCtrl() != null
      return this.available;
    },
    available: false,
    action_available: function(name_action) {
      return this.action_callback(name_action) != null && this.action_trigger(name_action);
    },
    action_callback: function(name_action) {
      var idx_form = forms.indexOf(this._visibleCtrl());
      var callbacks = null;
      var callback = null;
      angular.forEach(callback_form, function(value, key) {
        if (value.id == idx_form) {
          callbacks = value.callbacks;
        }
      });
      if (callbacks != null) {
        angular.forEach(callbacks, function(value, key) {
          if (value.name == name_action) {
            callback = value;
          }
        });
      }
      return callback;
    },
    action_trigger: function(name_action) {
      var idx_form = forms.indexOf(this._visibleCtrl());
      var triggers = null;
      var trigger = true;
      angular.forEach(triggers_form, function(value, key) {
        if (key == idx_form) {
          triggers = value;
        }
      });
      if (triggers != null) {
        angular.forEach(triggers, function(value, key) {
          if (key == name_action) {
            if (value != null)
              trigger = value;
          }
        });
      }
      return trigger;
    },
    call_action: function(name) {
      this.action_callback(name).callback();
    },
    _visibleCtrl: function() {
      var visibleCtrl = null;
      angular.forEach(forms, function(value, key) {
        if (visibleCtrl != null && $(value).is(':visible')) {
          console.log("Cannot manage many ctrl....");
        }
        if (visibleCtrl == null && $(value).is(':visible')) {
          visibleCtrl = value;
        }
      });
      return visibleCtrl;
    }
  };
});

editFormManager.directive('editFormControl', ['$timeout', function($timeout) {
  return {
    restrict: 'A',
    scope: {
      save: "=save",
      trigger: "=trigger",
      edit: "=edit",
      cancel: "=cancel",
      delete: "=delete",
    },
    compile: function(element, attr) {
      if (!attr.save) {
        attr.save = null;
      }
      if (!attr.edit) {
        attr.edit = null;
      }
      if (!attr.cancel) {
        attr.cancel = null;
      }
      if (!attr.delete) {
        attr.delete = null;
      }
    },
    controller: ['$scope', 'loEditFormManager', '$element', function($scope, loEditFormManager, $element) {
      var actions = [];
      if ($scope.save != null) {
        actions.push(new Callback('save', $scope.save));
      }
      if ($scope.edit != null) {
        actions.push(new Callback('edit', $scope.edit));
      }
      if ($scope.cancel != null) {
        actions.push(new Callback('cancel', $scope.cancel));
      }
      if ($scope.delete != null) {
        actions.push(new Callback('delete', $scope.delete));
      }
      $timeout(function() {
        loEditFormManager.add($element, actions, $scope.trigger);

        var config = {
          attributes: true
        };
        var observer = new MutationObserver(function(mutations) {
          $scope.$apply(function() {
            loEditFormManager.isavailable();
          });
        });
        $($element).parents().map(function() {
          return observer.observe(this, config);
        });
        observer.observe($($element).get(0), config);
      });
    }],
  }
}]);
from simulation.environment.environment import Environment

class GeodesicEnvironment(Environment):

    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def getInstance():
        """ Static access method. """
        if GeodesicEnvironment.__instance == None:
            GeodesicEnvironment()
        return GeodesicEnvironment.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if GeodesicEnvironment.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            GeodesicEnvironment.__instance = self
            super(GeodesicEnvironment, self).__init__()

    def getLayer(self, layer_name):
        """
            Return layer
        :param layer_name: GeoDataFrame containing all spatial elements of that layer
        :return:
        """
        return self.layer[layer_name]

    def addLayer(self, layer_name, layer):
        """
        Add a new layer to the environment. Typically, we assume a natural ordering of the layers (i.e., first layer is finest)
        :param layer_name: Layer name
        :param layer: Layer object stored as a Geopandas DataFrame
        :return:
        """
        self.layer[layer_name] = layer



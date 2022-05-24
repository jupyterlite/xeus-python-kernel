Configuration
=============

Pre-install packages
--------------------

xeus-python allows you to pre-install packages in the Python runtime.

For example, if you want to install NumPy, Matplotlib and ipyleaflet, it can be done with the following command:

.. code::

    jupyter lite build --XeusPythonEnv.packages=numpy,matplotlib,ipyleaflet

The same can be achieved through a `jupyterlite_config.json` file:

.. code::

    {
        "XeusPythonEnv": {
            "packages": ["numpy", "matplotlib", "ipyleaflet"]
        }
    }

Then those packages are usable directly:

.. replite::
   :kernel: xeus-python
   :height: 600px

    %matplotlib inline

    import matplotlib.pyplot as plt
    import numpy as np

    fig = plt.figure()
    plt.plot(np.sin(np.linspace(0, 20, 100)))
    plt.show();
